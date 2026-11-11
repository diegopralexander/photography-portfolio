// Draws the link-preview card (1200 x 630, black with the logo) to the given PNG path.
// Usage: swift tools/sharecard.swift share-card.png
import AppKit

let size = NSSize(width: 1200, height: 630)
let rep = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: 1200, pixelsHigh: 630,
                           bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
                           colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
rep.size = size
NSGraphicsContext.saveGraphicsState()
NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)
NSColor.black.setFill()
NSRect(origin: .zero, size: size).fill()

func draw(_ text: String, font: NSFont, kern: CGFloat, color: NSColor, baseline: CGFloat) {
    let attributes: [NSAttributedString.Key: Any] = [.font: font, .kern: kern, .foregroundColor: color]
    let string = NSAttributedString(string: text, attributes: attributes)
    let width = string.size().width - kern   // the last letter's spacing is not visible
    string.draw(at: NSPoint(x: (size.width - width) / 2, y: baseline))
}

let bold = NSFont(name: "HelveticaNeue-Bold", size: 84) ?? NSFont.boldSystemFont(ofSize: 84)
let light = NSFont(name: "HelveticaNeue", size: 30) ?? NSFont.systemFont(ofSize: 30)
draw("PETER&ALEXANDER", font: bold, kern: 2, color: .white, baseline: 300)
draw("MEDIA", font: light, kern: 18, color: NSColor(white: 1, alpha: 0.7), baseline: 232)
NSGraphicsContext.restoreGraphicsState()

let png = rep.representation(using: .png, properties: [:])!
try png.write(to: URL(fileURLWithPath: CommandLine.arguments[1]))
