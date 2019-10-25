#!/usr/bin/env kscript

@file:DependsOn("org.yaml:snakeyaml:1.24")
@file:DependsOn("org.jetbrains.kotlinx:kotlinx-coroutines-core:1.2.1")

import ExecutionState.*
import org.yaml.snakeyaml.Yaml
import org.yaml.snakeyaml.constructor.Constructor
import java.io.*
import java.lang.Exception
import java.lang.StringBuilder
import java.net.URLEncoder
import java.text.SimpleDateFormat
import java.util.*
import java.util.concurrent.TimeUnit

val parser = Yaml(Constructor(Project::class.java))

sealed class ExecutionState {
    object Done : ExecutionState()
    data class Timeout(val cmd: String, val timeLimit: TimeLimit) : ExecutionState()
    data class Error(val cmd: String, val code: Int) : ExecutionState()
}

data class Project(
    var path: String = "",
    var shortcuts: Map<String, String>? = null,
    var iterations: Int = 0,
    var versioning: Versioning? = null,
    var compile: String = "",
    var execute: String = "",
    var experiments: List<Experiment> = emptyList(),
    var measures: List<String> = emptyList(),
    var stats: List<String> = emptyList(),
    var timeout: TimeLimit? = null,
    var comments: String? = null
) {
    fun restore(cmd: String): String {
        var cmd = cmd.replace("{PROJECT}", path)
        val shortcuts = shortcuts
        return if (shortcuts == null || shortcuts.isEmpty()) {
            cmd
        } else {
            var old: String
            do {
                old = cmd
                for ((label, text) in shortcuts) {
                    cmd = cmd.replace("{$label}", text)
                }
                cmd = cmd.replace("{PROJECT}", path)
            } while (cmd != old)
            cmd
        }
    }
}

data class Versioning(
    var repository: String = "",
    var commit: String = "",
    var authentication: Boolean? = null
)

data class Experiment(
    var name: String = "",
    var parameters: List<String> = emptyList(),
    var disable: Boolean? = null,
    var timeout: TimeLimit? = null,
    var level: Int? = null
)

data class TimeLimit(
    var duration: Long = 0,
    var unit: String = "SECONDS"
)

fun main(args: Array<String>) {
    try {
        val project = parser.load(File(args[0]).reader()) as Project
        val folder = File(args[0].substringBeforeLast('.'))
        val configFileName = args[0].substringAfterLast('/').substringBeforeLast('.')
        project.path = project.path.replace("{FILE}", args[0].substringBeforeLast('.'))
        val verbose = "-v" in args || "--verbose" in args

        init(project, folder)
        if ("-g" in args || "--git" in args) {
            fetch(project)
        }

        if ("-b" in args || "--build" in args) {
            build(project, verbose)
        }

        if ("--clean" in args) {
            clean(project, folder, configFileName)
        }

        if ("-r" in args || "--run" in args) {
            execute(project, folder, configFileName, verbose)
        }

    } catch (e: Exception) {
        System.err.println(e)
    }

}

fun init(project: Project, folder: File) {
    File(project.path).mkdirs()
    folder.mkdirs()

    for (experiment in project.experiments) {
        val expFolder = folder / "results" / experiment.name
        expFolder.mkdirs()
    }
}

fun fetch(project: Project) {
    val versioning = project.versioning ?: panic("versioning field is not filled")

    val path = File(project.path)
    if (path.exists() && !path.isDirectory) panic("${path.name} is not a directory")

    val fetch = if (path.listFiles().isNotEmpty()) {
        print("Some files are in the source directory (${project.path}). Would you erase them [y\\N]? ")
        var response:String
        do {
            response = readLine()!!
        } while (response !in listOf("y", "Y", "n", "N", ""))

        val erase = response in listOf("y", "Y")
        if(erase) {
            path.deleteRecursively()
            path.mkdirs()
        }
        erase
    } else {
        true
    }

    if (fetch) {
        val gitClone = if (versioning.authentication == true) {
            val (protocol, url) = versioning.repository.split("://")
            print("Username for ${versioning.repository}: ")
            val username = URLEncoder.encode(readLine()!!, "UTF-8")
            print("Password for ${versioning.repository}: ")
            val password = URLEncoder.encode(readLine()!!, "UTF-8")
            cmd("git clone $protocol://$username:$password@$url ${project.path}")
        } else {
            cmd("git clone ${versioning.repository} ${project.path}")
        }
        if (gitClone != Done) panic(gitClone)

        val checkout =
            cmd("git --git-dir ${project.path}/.git --work-tree ${project.path} checkout ${versioning.commit}")
        if (checkout != Done) panic(checkout)
    } else {
        println("Skip fetch")
    }

}

fun build(project: Project, verbose: Boolean) {
    println("Compile executable")
    val build = cmd(project.restore(project.compile), verbose = verbose)
    if (build != Done) {
        panic(build)
    } else {
        println("Done")
    }
}

fun clean(project: Project, folder: File, configFileName: String) {
    val resultsFolder = folder / "results"
    for (experiment in project.experiments) {
        val expFolder = resultsFolder / experiment.name
        for (file in expFolder.listFiles()) {
            file.delete()
        }
    }
    val summaryCsv = resultsFolder / "$configFileName.csv"
    summaryCsv.delete()
}

fun execute(project: Project, folder: File, configFileName: String, verbose: Boolean) {
    val resultsFolder = folder / "results"
    val summary = resultsFolder / "$configFileName.csv"
    if (!summary.exists()) {
        summary.createNewFile()
        summary.writer().apply {
            append(CSV.header(project))
        }.close()
    }

    for (experiment in project.experiments.sortedBy { it.level ?: 0 }) {
        val expFolder = resultsFolder / experiment.name
        val lockFile = expFolder / "_lock"
        if (!lockFile.exists()) {
            lockFile.createNewFile()
            val now = Date()
            val hours = SimpleDateFormat("HH:mm")
            val date = SimpleDateFormat("MMM dd, YYY")
            println("Starting experiment [${experiment.name}] @ ${hours.format(now)} the ${date.format(now)}")

            val times = LongArray(project.iterations)
            for (iter in 0 until project.iterations) {
                val log = expFolder / "$iter.csv"
                if (!log.exists()) log.createNewFile()
                val start = System.currentTimeMillis()
                val status = cmd(
                    project.restore(project.execute),
                    args = experiment.parameters,
                    verbose = verbose,
                    redirect = log,
                    timeout = experiment.timeout ?: project.timeout
                )

                when (status) {
                    is Error, is Timeout -> {
                        FileWriter(log, true).apply {
                            append(status.toString() + "\n\n")
                        }.close()
                        times.fill(-1000)
                    }
                    is Done -> {
                        val end = System.currentTimeMillis()
                        times[iter] = end - start
                    }
                }
                if (status !is Done) break
            }
            FileWriter(summary, true).apply {
                append(CSV.row(project, experiment, expFolder / "0.csv", times))
            }.close()
        } else if (verbose) {
            println("Skip experiment [${experiment.name}]")
        }
    }
}

/* UTILS */
fun panic(reason: Any): Nothing = throw RuntimeException(reason.toString())

operator fun File.div(child: String) = File(this, child)

fun cmd(
    cmd: String,
    args: List<String> = emptyList(),
    redirect: File? = null,
    verbose: Boolean = false,
    timeout: TimeLimit? = null
): ExecutionState {

    var fullCmd = cmd
    if (args.isNotEmpty()) fullCmd += " " + args.joinToString(" ")

    println("> $fullCmd")
    val fileWriter = redirect?.bufferedWriter()

    return try {
        val process = Runtime.getRuntime().exec(fullCmd)

        val stdInput = process.inputStream.bufferedReader()
        val stdError = process.errorStream.bufferedReader()

        if (redirect != null) {
            Pipe(stdInput, redirect.bufferedWriter(), verbose).start()
            Pipe(stdError, redirect.bufferedWriter(), verbose).start()
        }

        if (timeout != null) {
            if (!process.waitFor(timeout.duration, TimeUnit.valueOf(timeout.unit))) {
                process.destroy()
            }
        }
        process.waitFor()
        when (process.exitValue()) {
            0 -> Done
            143 -> Timeout(cmd, timeout!!)
            else -> Error(cmd, process.exitValue())
        }
    } catch (e: Exception) {
        e.printStackTrace()
        Error(cmd, -1)
    } finally {
        fileWriter?.close()
    }
}

class Pipe(
    val reader: BufferedReader,
    val writer: BufferedWriter,
    val stdOut: Boolean
) : Thread() {
    override fun run() {
        try {
            var line: String? = reader.readLine()
            while (line != null) {
                writer.write(line + "\n")
                writer.flush()
                if (stdOut) {
                    println(line)
                }
                line = reader.readLine()
            }
        } catch (ioe: IOException) {
        }
    }
}

object Stats {

    fun min(records: LongArray) = records.min()!!
    fun max(records: LongArray) = records.max()!!
    fun mean(records: LongArray) = if (records.isEmpty()) 0L else records.sum() / records.size
    fun time(records: LongArray) = records[0]
    fun std(records: LongArray): Long {
        val N = records.size
        val mean = mean(records)
        var sum = 0L
        for (i in 0 until records.size) {
            val x = records[i]
            sum += (x - mean) * (x - mean)
        }
        return (sum / (N - 1))
    }

}

object CSV {

    fun header(project: Project): String {
        val header = StringBuilder()
        header.append("\"Experiment\",")
        for (measure in project.measures.filter { it != "skip" }) {
            header.append("\"$measure\",")
        }
        for (stat in project.stats) {
            header.append("\"$stat\",")
        }
        header.append("\"args\",")
        header.append("\n")
        return header.toString()
    }

    fun row(project: Project, experiment: Experiment, logFile: File?, times: LongArray): String {
        val row = StringBuilder()
        row.append("\"${experiment.name}\",")

        val content = logFile?.readLines()?.last()?.split(",")
        for (i in 0 until project.measures.size) {
            if (project.measures[i] != "skip") {
                if (content != null && content.size > i) {
                    row.append(content[i])
                }
                row.append(",")
            }
        }

        for (stat in project.stats) {
            val fn = when (stat) {
                "min", "MIN" -> Stats::min
                "max", "MAX" -> Stats::max
                "mean", "MEAN", "avg", "AVG" -> Stats::mean
                "std", "STD" -> Stats::std
                "time", "TIME" -> Stats::time
                else -> null
            }

            if (fn != null) {
                val statTime = fn(times) / 1000
                if (statTime >= 0) row.append(statTime)
                else row.append("nan")
            } else {
                row.append("nan")
            }
            row.append(",")

        }
        row.append(experiment.parameters.joinToString(",") { it.replace(',', ' ') })
        row.append(",")
        row.append("\n")
        return row.toString()
    }

}
