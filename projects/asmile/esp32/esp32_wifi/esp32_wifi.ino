#include <WiFi.h>
#include <WebServer.h>
#include <ESPmDNS.h>
#include <ArduinoOTA.h>

const char* SSID = "SpadaBike";
const char* PASS = "sp@d@bike2020";
const char* HOSTNAME = "esp32";
const char* OTA_PASS = "otabike";   // password per il flash remoto

// --- IP statico ---
IPAddress IP_STATICO(192, 168, 1, 134);
IPAddress GATEWAY   (192, 168, 1, 1);
IPAddress SUBNET    (255, 255, 255, 0);
IPAddress DNS1      (192, 168, 1, 1);
IPAddress DNS2      (8, 8, 8, 8);

WebServer server(80);

String page() {
  String s = "<!doctype html><html><head><meta charset='utf-8'>";
  s += "<meta name='viewport' content='width=device-width,initial-scale=1'>";
  s += "<title>ESP32</title><style>body{font-family:sans-serif;margin:40px;background:#111;color:#eee}";
  s += "h1{color:#4cafef}code{background:#222;padding:2px 6px;border-radius:4px}</style></head><body>";
  s += "<h1>ESP32 online 🚴</h1>";
  s += "<p>IP: <code>" + WiFi.localIP().toString() + "</code></p>";
  s += "<p>MAC: <code>" + WiFi.macAddress() + "</code></p>";
  s += "<p>RSSI: <code>" + String(WiFi.RSSI()) + " dBm</code></p>";
  s += "<p>Uptime: <code>" + String(millis()/1000) + " s</code></p>";
  s += "<p>Host OTA: <code>esp32.local</code></p>";
  s += "</body></html>";
  return s;
}

void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.println();
  Serial.printf("Connessione a %s ...\n", SSID);
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  WiFi.setHostname(HOSTNAME);
  if (!WiFi.config(IP_STATICO, GATEWAY, SUBNET, DNS1, DNS2))
    Serial.println("WARN: config IP statico fallita");
  WiFi.begin(SSID, PASS);

  int t = 0;
  while (WiFi.status() != WL_CONNECTED && t < 40) {
    delay(500); Serial.print("."); t++;
  }
  Serial.println();
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("WIFI OK");
    Serial.print("IP:   "); Serial.println(WiFi.localIP());
    Serial.print("MAC:  "); Serial.println(WiFi.macAddress());

    // --- OTA ---
    ArduinoOTA.setHostname(HOSTNAME);
    ArduinoOTA.setPassword(OTA_PASS);
    ArduinoOTA.onStart([]() { Serial.println("OTA: inizio aggiornamento"); });
    ArduinoOTA.onEnd([]()   { Serial.println("\nOTA: fine"); });
    ArduinoOTA.onProgress([](unsigned int p, unsigned int tot) {
      Serial.printf("OTA: %u%%\r", (p * 100) / tot);
    });
    ArduinoOTA.onError([](ota_error_t e) { Serial.printf("OTA errore [%u]\n", e); });
    ArduinoOTA.begin();
    Serial.println("OTA pronto (host=esp32, pass=otabike)");

    if (MDNS.begin(HOSTNAME)) Serial.println("mDNS: http://esp32.local");
    server.on("/", []() { server.send(200, "text/html", page()); });
    server.begin();
    Serial.println("Web server attivo su porta 80");

    // ===== IL TUO CODICE DI SETUP VA QUI SOTTO (non toccare le righe sopra) =====

    // ===========================================================================
  } else {
    Serial.println("WIFI FALLITO (controlla password / 2.4GHz)");
  }
}

void loop() {
  ArduinoOTA.handle();      // <-- NON rimuovere: senza questa perdi il flash via WiFi
  server.handleClient();

  // ===== IL TUO CODICE DI LOOP VA QUI (non toccare le 2 righe sopra) =====

  // =======================================================================

  static unsigned long last = 0;
  if (millis() - last > 10000) {
    last = millis();
    Serial.printf("stato=%d  IP=%s  RSSI=%ld\n",
      WiFi.status(), WiFi.localIP().toString().c_str(), WiFi.RSSI());
  }
}
