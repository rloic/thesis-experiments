package com.github.rloic.kt

private val allParams = mapOf<String, List<Parameters>>(
   "aes128" to listOf(
      Parameters(3, 5, 1), 
      Parameters(4, 12, 2), 
      Parameters(5, 17, 3)
   ),
   "aes192" to listOf(
      Parameters(3, 1, 1),
      Parameters(4, 4, 1),
      Parameters(5, 5, 1),
      Parameters(6, 10, 1),
      Parameters(7, 13, 2),
      Parameters(8, 18, 2),
      Parameters(9, 24, 3),
      Parameters(10, 27, 3)
   ),
   "aes256" to listOf(
      Parameters(3, 1, 1),
      Parameters(4, 3, 1),
      Parameters(5, 3, 1),
      Parameters(6, 5, 1),
      Parameters(7, 5, 1),
      Parameters(8, 10, 2),
      Parameters(9, 15, 2),
      Parameters(10, 16, 3),
      Parameters(11, 20, 4),
      Parameters(12, 20, 5),
      Parameters(13, 24, 6),
      Parameters(14, 24, 7)
   )
)
 
fun main() {
   print("Versions: ")
   var userInput = readLine()!!
   val versions = if (userInput == "*") listOf("AES-128", "AES-192", "AES-256") 
   else userInput.split(", ")
   
   val parameters = mutableMapOf<String, List<Parameters>>()
   for (version in versions) {
      print("Parameters for $version: ")
      
      userInput = readLine()!!
      parameters[version] = if (userInput == "*") {
         allParams[version.toLowerCase().replace("-", "")]!!
      } else {
         userInput.split(", ").map { param ->
         val args = param.split("::").map(String::toInt)
         Parameters(args[0], args[1], args.nth(2))
         }
      }
   }
   // println(parameters)
   print("Heuristics: ")
   val heuristics = readLine()!!.split(", ")
   // println(heuristics)
   
   print("Restarts coefficients: ")
   val restarts = readLine()!!.split(", ").map(String::toInt)
   
   print("Orders: ")
   val orders = readLine()!!.split(", ")
 
   for (version in versions) {
      for ((round, nbSBoxes, level) in parameters[version]!!) {
         for (heuristic in heuristics) {
            for (order in orders) {
               for (restart in restarts) {
                  println("  - name: $version-$round-${nbSBoxes}__${heuristic}__${order}__${restart}")
                  println("    parameters: [$version, $round, $nbSBoxes, $heuristic, $restart, $order]")
                  if (level != null) {
                     println("    level: $level")
                  }
               }
            }
         }
      }
   }
}

fun <T> List<T>.nth(n: Int): T? = if (n >= size) null else this[n]
 
data class Parameters(val nbRounds: Int, val nbSBoxes: Int, val level: Int? = null)
