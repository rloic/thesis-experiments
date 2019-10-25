package com.github.rloic.kt
 
fun main() {
   print("Versions: ")
   val versions = readLine()!!.split(", ")
   //println(versions)
   
   val parameters = mutableMapOf<String, List<Parameters>>()
   for (version in versions) {
      print("Parameters for $version: ")
      parameters[version] = readLine()!!.split(", ").map { param ->
         val (round, nbSBoxes) = param.split("::").map(String::toInt)
         Parameters(round, nbSBoxes)
      }
   }
   // println(parameters)
   print("Heuristics: ")
   val heuristics = readLine()!!.split(", ")
   // println(heuristics)
 
   for (version in versions) {
      for ((round, nbSBoxes) in parameters[version]!!) {
         for (heuristic in heuristics) {
            println("  - name: $version-$round-${nbSBoxes}__$heuristic")
            println("    parameters: [$version, $round, $nbSBoxes, $heuristic]")
         }
      }
   }
}
 
data class Parameters(val nbRounds: Int, val nbSBoxes: Int)
