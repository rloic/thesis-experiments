package com.github.rloic.kt
 
val all = (3..20).map { n -> Parameters(n, n) }

fun main() {   
   print("Parameters: ")
   val text = readLine()!!.split(", ")
   
   val parameters = if (text[0] == "*") all else text.map { param ->
      val (round, nbSBoxes) = param.split("::").map(String::toInt)
      Parameters(round, nbSBoxes)
   }
   
   print("Restarts coeff: ")
   val coeffs = readLine()!!.split(", ").map(String::toInt)
   
   // println(parameters)
   print("Heuristics: ")
   val heuristics = readLine()!!.split(", ")
   // println(heuristics)
 
   for ((round, nbSBoxes) in parameters) {
      for (heuristic in heuristics) {
         for (coeff in coeffs) {
            println("  - name: Midori-128-$round-${nbSBoxes}__${heuristic}__$coeff")
            println("    parameters: [$round, $nbSBoxes, $heuristic, $coeff]")
         }
      }
   }
}
 
data class Parameters(val nbRounds: Int, val nbSBoxes: Int)
