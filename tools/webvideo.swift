// Shrinks a video for the web: H.264 + AAC in an .mp4, scaled so its long edge is
// at most 1920 px (or the given size), at a bitrate browsers stream comfortably.
// Also prints "width height".
// Usage: swift webvideo.swift <source> <output.mp4> [video kbit/s] [long edge px]
import AVFoundation
import Foundation

let args = CommandLine.arguments
guard args.count >= 3 else { fatalError("usage: webvideo <source> <output.mp4> [kbps]") }
let source = URL(fileURLWithPath: args[1])
let output = URL(fileURLWithPath: args[2])
let kbps = args.count > 3 ? Int(args[3]) ?? 5000 : 5000
let edge = CGFloat(args.count > 4 ? Int(args[4]) ?? 1920 : 1920)
try? FileManager.default.removeItem(at: output)

let asset = AVURLAsset(url: source)
guard let videoTrack = asset.tracks(withMediaType: .video).first else { fatalError("no video track") }
let audioTrack = asset.tracks(withMediaType: .audio).first

let natural = videoTrack.naturalSize
let scale = min(1, edge / max(natural.width, natural.height))
let width = Int(natural.width * scale / 2) * 2
let height = Int(natural.height * scale / 2) * 2

let reader = try AVAssetReader(asset: asset)
let writer = try AVAssetWriter(outputURL: output, fileType: .mp4)
writer.shouldOptimizeForNetworkUse = true

let videoOut = AVAssetReaderTrackOutput(track: videoTrack, outputSettings: [
    kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_420YpCbCr8BiPlanarVideoRange
])
reader.add(videoOut)
let videoIn = AVAssetWriterInput(mediaType: .video, outputSettings: [
    AVVideoCodecKey: AVVideoCodecType.h264,
    AVVideoWidthKey: width,
    AVVideoHeightKey: height,
    AVVideoCompressionPropertiesKey: [
        AVVideoAverageBitRateKey: kbps * 1000,
        AVVideoProfileLevelKey: AVVideoProfileLevelH264HighAutoLevel,
        AVVideoMaxKeyFrameIntervalKey: 60
    ]
])
videoIn.transform = videoTrack.preferredTransform
videoIn.expectsMediaDataInRealTime = false
writer.add(videoIn)

var audioOut: AVAssetReaderTrackOutput?
var audioIn: AVAssetWriterInput?
if let track = audioTrack {
    let out = AVAssetReaderTrackOutput(track: track, outputSettings: [
        AVFormatIDKey: kAudioFormatLinearPCM
    ])
    reader.add(out)
    let input = AVAssetWriterInput(mediaType: .audio, outputSettings: [
        AVFormatIDKey: kAudioFormatMPEG4AAC,
        AVNumberOfChannelsKey: 2,
        AVSampleRateKey: 44100,
        AVEncoderBitRateKey: 128_000
    ])
    input.expectsMediaDataInRealTime = false
    writer.add(input)
    audioOut = out
    audioIn = input
}

guard reader.startReading() else { fatalError("read failed: \(String(describing: reader.error))") }
guard writer.startWriting() else { fatalError("write failed: \(String(describing: writer.error))") }
writer.startSession(atSourceTime: .zero)

let group = DispatchGroup()
func pump(_ input: AVAssetWriterInput, _ out: AVAssetReaderTrackOutput, _ label: String) {
    group.enter()
    input.requestMediaDataWhenReady(on: DispatchQueue(label: label)) {
        while input.isReadyForMoreMediaData {
            if let sample = out.copyNextSampleBuffer() {
                if !input.append(sample) { input.markAsFinished(); group.leave(); return }
            } else {
                input.markAsFinished(); group.leave(); return
            }
        }
    }
}
pump(videoIn, videoOut, "video")
if let input = audioIn, let out = audioOut { pump(input, out, "audio") }
group.wait()

let done = DispatchSemaphore(value: 0)
writer.finishWriting { done.signal() }
done.wait()
guard writer.status == .completed, reader.status == .completed else {
    fatalError("failed: \(String(describing: writer.error ?? reader.error))")
}

// Report the size as displayed (after the track's rotation).
let shown = CGSize(width: width, height: height).applying(videoTrack.preferredTransform)
print("\(Int(abs(shown.width))) \(Int(abs(shown.height)))")
