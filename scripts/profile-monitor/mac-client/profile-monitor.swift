// profile-monitor.swift — daemon eventi sessione macOS
// Esegui sul profilo `balizero` di ogni Mac dipendente
// Notifica check-out reali (logout/switch user/shutdown), ignora sleep/lock
//
// Compila: swiftc -O profile-monitor.swift -o profile-monitor
// Esegui:  ./profile-monitor [employee_name]

import Cocoa
import Foundation

// ─── Config ─────────────────────────────────────────────────────────────
let WRAPPER_URL = "http://100.107.22.111:9099/checkout"
let LOG_PATH = "\(NSHomeDirectory())/Library/Logs/balizero-profile-events.log"

// Argomento: employee identifier (es. "surya")
let employee: String = {
    if CommandLine.arguments.count >= 2 {
        return CommandLine.arguments[1]
    }
    return NSUserName()  // fallback
}()

let hostname = ProcessInfo.processInfo.hostName

// ─── Logging ───────────────────────────────────────────────────────────
let dateFormatter: DateFormatter = {
    let df = DateFormatter()
    df.dateFormat = "yyyy-MM-dd HH:mm:ss xxx"
    return df
}()

func logEvent(_ kind: String, payload: String = "") {
    let ts = dateFormatter.string(from: Date())
    let line = "\(ts)  \(kind.padding(toLength: 10, withPad: " ", startingAt: 0))  user=\(employee)  host=\(hostname)  \(payload)\n"
    print(line, terminator: "")
    fflush(stdout)
    if let data = line.data(using: .utf8) {
        if let fh = FileHandle(forWritingAtPath: LOG_PATH) {
            fh.seekToEndOfFile()
            fh.write(data)
            try? fh.close()
        } else {
            try? data.write(to: URL(fileURLWithPath: LOG_PATH))
        }
    }
}

// ─── HTTP POST al wrapper Pro ──────────────────────────────────────────
func postCheckout(consoleOwner: String) {
    let payload: [String: Any] = [
        "employee": employee,
        "event": "CHECKOUT",
        "timestamp": ISO8601DateFormatter().string(from: Date()),
        "console_owner": consoleOwner,
        "hostname": hostname,
    ]
    guard let body = try? JSONSerialization.data(withJSONObject: payload) else {
        logEvent("ERROR", payload: "json_serialize_failed")
        return
    }
    var req = URLRequest(url: URL(string: WRAPPER_URL)!)
    req.httpMethod = "POST"
    req.setValue("application/json", forHTTPHeaderField: "Content-Type")
    req.httpBody = body
    req.timeoutInterval = 5

    let sem = DispatchSemaphore(value: 0)
    let task = URLSession.shared.dataTask(with: req) { data, response, error in
        if let error = error {
            logEvent("POST_FAIL", payload: "error=\(error.localizedDescription)")
        } else if let http = response as? HTTPURLResponse {
            let bodyStr = data.flatMap { String(data: $0, encoding: .utf8) } ?? ""
            logEvent("POST_OK", payload: "status=\(http.statusCode) body=\(bodyStr.prefix(100))")
        }
        sem.signal()
    }
    task.resume()
    _ = sem.wait(timeout: .now() + 6)
}

// ─── Console owner check ───────────────────────────────────────────────
func currentConsoleOwner() -> String {
    var stat_buf = stat()
    if stat("/dev/console", &stat_buf) == 0 {
        let pwd = getpwuid(stat_buf.st_uid)
        if let p = pwd, let name = p.pointee.pw_name {
            return String(cString: name)
        }
        return "uid:\(stat_buf.st_uid)"
    }
    return "unknown"
}

// ─── Event handlers ────────────────────────────────────────────────────
let nc = NSWorkspace.shared.notificationCenter

// CHECK-IN (sessione del nostro utente attivata)
nc.addObserver(forName: NSWorkspace.sessionDidBecomeActiveNotification, object: nil, queue: nil) { _ in
    logEvent("CHECKIN", payload: "console=\(currentConsoleOwner())")
}

// CHECK-OUT REALE (logout / Fast User Switching verso altro profilo)
nc.addObserver(forName: NSWorkspace.sessionDidResignActiveNotification, object: nil, queue: nil) { _ in
    let owner = currentConsoleOwner()
    logEvent("CHECKOUT", payload: "console=\(owner)")
    postCheckout(consoleOwner: owner)
}

// SLEEP — registrato ma IGNORATO (no POST)
nc.addObserver(forName: NSWorkspace.willSleepNotification, object: nil, queue: nil) { _ in
    logEvent("SLEEP", payload: "(ignored)")
}

// WAKE — registrato ma IGNORATO
nc.addObserver(forName: NSWorkspace.didWakeNotification, object: nil, queue: nil) { _ in
    logEvent("WAKE", payload: "(ignored)")
}

// SHUTDOWN — equivalente a CHECKOUT
nc.addObserver(forName: NSWorkspace.willPowerOffNotification, object: nil, queue: nil) { _ in
    let owner = currentConsoleOwner()
    logEvent("SHUTDOWN", payload: "console=\(owner)")
    postCheckout(consoleOwner: owner)
}

// Avvio
logEvent("DAEMON_START", payload: "employee=\(employee) wrapper=\(WRAPPER_URL)")
RunLoop.main.run()
