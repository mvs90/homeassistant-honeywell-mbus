# Deutsche Anleitung

Diese Integration liest einen Honeywell EEM400C-D-M direkt über kabelgebundenen
M-Bus und eine transparente TCP-/RS232-Brücke. Referenzanschluss: W&T
Com-Server++ → Relay PW20 → Honeywell. MQTT, Shell-Befehle und ein
Verwaltungskennwort des W&T werden nicht benötigt.

Der erste Entwicklungsstand unterstützt den geprüften HON-Telegrammaufbau mit
Geräteversionsbyte 0x15 und 152 Byte Antwortlänge. Andere Modelle oder Profile
werden noch nicht als unterstützt ausgegeben. Pro TCP-Brücke ist ein Zähler
vorgesehen. Ein separater Hardware-Abnahmetest steht vor der Produktivmigration an.

## Einrichtung

Das Repository kann nach Bereitstellung über HACS als benutzerdefiniertes
Integrationsrepository installiert werden. Es ist noch nicht im Standard-Store
eingereicht. Nach dem Kopieren der Integration ist ein HA-Neustart für ihre
Erkennung notwendig; bei der lokalen Entwicklung wird die produktive Instanz
nicht verändert.

Unter **Einstellungen → Geräte & Dienste → Integration hinzufügen → Honeywell
M-Bus** Host/IP, Rohdaten-TCP-Port (oft 8000) und Primäradresse eingeben. Der erste
Verbindungstest prüft Identität und zwei frische Antworten. Andere Leser auf dem
Bus vorher stoppen. Die Integration kennt deren Existenz außerhalb von HA nicht.

Am Gateway müssen bereits 8 Datenbits, gerade Parität, 1 Stoppbit und kein
Handshake eingestellt sein. Die Baudrate muss zum Zähler passen. Sie wird von
dieser Integration nicht geändert. Auch Zählerreset, Relais, Firmwareupdate oder
Gateway-Verwaltung sind bewusst keine Funktionen dieser Messintegration.

## Werte und Optionen

17 Sensoren sind standardmäßig aktiviert, drei zusätzliche Diagnose-Sensoren
zunächst deaktiviert. Gesamtenergie wird mit passender Geräte-/Zustandsklasse
bereitgestellt. Rücksetzbare Teilzähler werden nicht als Verbrauch verwendet.
Vorzeichen der Leistung bleiben erhalten; Einheiten werden aus den VIF-Feldern
bestimmt. Der Wandlerfaktor wird nicht nochmals auf bereits skalierte Werte
angewandt. 100-W-Stufen bleiben auch bei schneller Abfrage 100-W-Stufen.

Standardintervall: 2 Sekunden, Antwortzeitlimit: 1,5 Sekunden. Unter **Konfigurieren**
sind andere Werte möglich. Abfragen laufen nacheinander und können bei längeren
Antworten oder Wiederholungen länger dauern. Es handelt sich um Polling, nicht
um spontane Änderungsmeldungen. Die Verbindung bleibt normalerweise offen und
wird bei Fehlern neu aufgebaut. Es gibt keinen laufenden Festplatten-Cache.

Ausfälle führen zu **nicht verfügbar**, niemals zu erfundenen Nullwerten.
Herunterladbare Diagnosedaten schwärzen Host und Seriennummer und enthalten keine
Rohtelegramme. Eine geänderte IP kann über **Neu konfigurieren** eingetragen werden;
derselbe Zähler behält seine Kennungen. Ein neuer Zähler darf die bestehende
Energiehistorie nicht automatisch übernehmen.

Für den Umzug vorhandener MQTT-Sensoren ist die separate [Migrationsanleitung](MIGRATION.md)
maßgeblich. Der erste Entwicklungsstand führt diese Migration nicht selbst aus.
