module Main where

import Lang.Source
import Pass.EmbedRuntime
import Pass.ExposeBlocks
import Pass.FlattenBegins
import Pass.GenerateX64
import Pass.Normalize
import Pass.RemoveIfs
import Pass.RemoveJumps
import Pass.RemovePreds
import Pass.Sequentialize
import Pass.Uniquify
import Data.Int (Int64)

import Private.???

compiler :: RandomGen g => Eq a => g -> Program a -> String
compiler = _

deriveKeys :: Int -> [Int64]
deriveKeys seed = _
 
main :: IO ()
main = do
  flag <- getLine
  seedStr <- getLine
  let seed = read seedStr
      keys = deriveKeys seed
      gen = mkStdGen seed
  putStrLn $ compiler gen $ makeFlagChecker gen flag
