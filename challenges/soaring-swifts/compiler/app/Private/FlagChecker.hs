module Private.FlagChecker where

import Data.Bits (shiftL, shiftR, xor, (.&.), (.|.))
import Data.Char (ord)
import Data.Int
import Data.List (unfoldr)
import Lang.Source
import Data.Word (Word64)

type Keys = [Int64]

makeFlagChecker :: Keys -> String -> Program String
makeFlagChecker keys flag = _
