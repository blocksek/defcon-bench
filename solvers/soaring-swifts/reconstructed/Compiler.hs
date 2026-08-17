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
import Data.Bits (xor, shiftL, shiftR, (.&.))
import System.Random (RandomGen, mkStdGen)

import Private.FlagChecker

compiler :: (RandomGen g, Eq a) => g -> Program a -> String
compiler _ prog =
  unlines
    $ embedRuntime
    $ generateX64
    $ removePreds
    $ removeJumps
    $ removeIfs
    $ flattenBegins
    $ exposeBlocks
    $ normalize
    $ sequentialize
    $ uniquify prog

-- Derive per-round keys from the seed with a simple splitmix-ish LCG.
deriveKeys :: Int -> [Int64]
deriveKeys seed = go (fromIntegral seed `xor` 0x9e3779b97f4a7c15)
  where
    go :: Int64 -> [Int64]
    go s =
      let s' = s * 6364136223846793005 + 1442695040888963407
          out = mix s'
      in out : go s'
    mix :: Int64 -> Int64
    mix z0 =
      let z1 = (z0 `xor` (z0 `shiftR` 30)) * (-4658895280553007687)
          z2 = (z1 `xor` (z1 `shiftR` 27)) * (-7723592293110705685)
      in z2 `xor` (z2 `shiftR` 31)

main :: IO ()
main = do
  flag <- getLine
  seedStr <- getLine
  let seed = read seedStr
      keys = deriveKeys seed
      gen = mkStdGen seed
  putStrLn $ compiler gen $ makeFlagChecker keys flag
