// swift-tools-version: 5.9

import PackageDescription

let package = Package(
    name: "NuzStatus",
    platforms: [
        .macOS(.v13)
    ],
    products: [
        .executable(name: "NuzStatus", targets: ["NuzStatus"])
    ],
    targets: [
        .executableTarget(
            name: "NuzStatus",
            path: "Sources/NuzStatus"
        )
    ]
)
