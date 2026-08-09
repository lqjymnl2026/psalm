// ocr_tool.swift — 用 macOS Vision 框架做离线中文/英文文字识别
// 用法: ocr_tool <图片路径>   → 输出 JSON: [{text,x,y,w,h,conf}]（y 为归一化坐标，0=图片顶部）
import Foundation
import Vision
import ImageIO

guard CommandLine.arguments.count > 1 else {
    FileHandle.standardError.write("usage: ocr_tool <image>\n".data(using: .utf8)!)
    exit(2)
}
let path = CommandLine.arguments[1]
let url = URL(fileURLWithPath: path)
guard let src = CGImageSourceCreateWithURL(url as CFURL, nil),
      let cg = CGImageSourceCreateImageAtIndex(src, 0, nil) else {
    FileHandle.standardError.write("cannot load image\n".data(using: .utf8)!)
    exit(3)
}

let request = VNRecognizeTextRequest()
request.recognitionLevel = .accurate
request.usesLanguageCorrection = true
request.recognitionLanguages = ["zh-Hans", "en-US"]
request.minimumTextHeight = 0.008

let handler = VNImageRequestHandler(cgImage: cg, options: [:])
do { try handler.perform([request]) }
catch {
    FileHandle.standardError.write("vision failed: \(error)\n".data(using: .utf8)!)
    exit(4)
}

struct Line: Codable { let text: String; let x: Double; let y: Double; let w: Double; let h: Double; let conf: Double }
var lines: [Line] = []
for obs in request.results ?? [] {
    guard let cand = obs.topCandidates(1).first else { continue }
    let b = obs.boundingBox
    let x = Double(b.origin.x)
    let yTop = Double(1 - b.origin.y - b.size.height)
    lines.append(Line(text: cand.string, x: x, y: yTop,
                      w: Double(b.size.width), h: Double(b.size.height),
                      conf: Double(cand.confidence)))
}
lines.sort { a, b in
    if abs(a.y - b.y) > 0.012 { return a.y < b.y }
    return a.x < b.x
}
let enc = JSONEncoder()
enc.outputFormatting = [.prettyPrinted, .sortedKeys]
if let out = try? enc.encode(lines) {
    FileHandle.standardOutput.write(out)
}
