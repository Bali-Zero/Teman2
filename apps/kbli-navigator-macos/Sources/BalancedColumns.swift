import Foundation

/// Splits a text into n columns at the space nearest k·len/n (k = 1…n−1); joining the columns
/// back with single spaces reproduces the source exactly (spec §3.5). Pure: the view comes later.
enum BalancedColumns {
    static func split(_ s: String, into n: Int) -> [String] {
        let chars = Array(s)
        guard n > 1, chars.count > 0 else { return [s] }
        var cuts: [Int] = []          // indices of the single spaces that are dropped
        var prev = -1
        for k in 1..<n {
            let target = k * chars.count / n
            var best: Int? = nil
            var bestDist = Int.max
            var i = prev + 1
            while i < chars.count {
                if chars[i] == " " {
                    let d = abs(i - target)
                    if d < bestDist { best = i; bestDist = d }   // strict <: ties keep the earlier
                }
                i += 1
            }
            guard let cut = best else { break }
            cuts.append(cut)
            prev = cut
        }
        var out: [String] = []
        var start = 0
        for c in cuts {
            out.append(String(chars[start..<c]))
            start = c + 1
        }
        out.append(String(chars[start...]))
        return out
    }
}
