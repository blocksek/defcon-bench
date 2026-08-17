module Private.FlagChecker where

import Data.Bits (shiftL, shiftR, xor, (.&.), (.|.))
import Data.Char (ord)
import Data.Int
import Data.List (foldl')
import Lang.Source
import Data.Word (Word64)

type Keys = [Int64]

-- 8 ascii bytes -> little-endian Int64 word
packWord :: String -> Int64
packWord bs = fromIntegral (foldr (\c acc -> (acc `shiftL` 8) .|. fromIntegral (ord c)) (0 :: Word64) bs)

chunk8 :: String -> [String]
chunk8 [] = []
chunk8 xs = take 8 xs : chunk8 (drop 8 xs)

-- The per-word transform applied to an input word (as a Source Value),
-- parameterised by two keys. Bijective (odd multiplier) so equality is exact.
transformV :: Int64 -> Int64 -> Value a -> Value a
transformV k1 mult x =
  Mul (BitXor x (VNum k1)) (VNum (mult .|. 1))

-- Same transform evaluated concretely in Haskell (Int64 wraparound == x86 64-bit)
transformC :: Int64 -> Int64 -> Int64 -> Int64
transformC k1 mult x = (x `xor` k1) * (mult .|. 1)

-- true / false predicates (no native And; build conjunction with IfP)
pTrue :: Pred a
pTrue = Eq (VNum 0) (VNum 0)

pFalse :: Pred a
pFalse = Eq (VNum 0) (VNum 1)

conj :: [Pred a] -> Pred a
conj = foldr (\p acc -> IfP p acc pFalse) pTrue

makeFlagChecker :: Keys -> String -> Program String
makeFlagChecker keys flag = Module (Halt (conj checks))
  where
    ws = chunk8 flag                 -- 4 words for a 32-char secret
    nWords = length ws
    -- pull two keys per word
    keyPairs = [ (keys !! (2*i), keys !! (2*i+1)) | i <- [0 .. nWords - 1] ]
    checks =
      [ Eq (transformV k1 mult (InputWord (fromIntegral i)))
           (VNum (transformC k1 mult (packWord w)))
      | (i, w, (k1, mult)) <- zip3 [0 ..] ws keyPairs
      ]
