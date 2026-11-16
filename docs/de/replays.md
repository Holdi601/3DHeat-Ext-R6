---
title: "Replays"
nav_order: 3
lang: "de"
source: replays.md
source_hash: "358b28bf88ce"
nav_exclude: true
search_exclude: true
---
# Replays werden zu Matches {#replays-into-matches}

Siege bewahrt deine letzten Matches als *Match Replays* im Ordner
`MatchReplay` im Installationsordner des Spiels auf: ein Ordner pro Match,
eine `.rec`-Datei pro Runde (`Match-<Datum>-<id>/Match-<Datum>-<id>-R01.rec`).
Turnierveranstalter veröffentlichen Replays auch als Zip-Dateien.

## Deine eigenen Matches {#your-own-matches}

```text
heat3d-r6-replay --game "<dein Spielordner>" -o matches
```

liest den Ordner `MatchReplay` im angegebenen Spielordner und wandelt jedes
Match darin um. Jedes Match wird zu einer Datei:

```text
matches/r6_Clubhouse_2026-01-02-20-15-00.3dheat
```

## Andere Replays {#other-replays}

```text
heat3d-r6-replay "D:\Replays\Match-2026-01-02_20-15-00-123" -o matches     # ein Match-Ordner
heat3d-r6-replay "D:\Replays" -o matches                                    # jedes Match unter einem Ordner
heat3d-r6-replay "D:\Downloads\tournament-day-1.zip" -o matches             # ein Zip, direkt gelesen
heat3d-r6-replay info "D:\Replays\Match-...\Match-...-R01.rec"              # was eine Runde enthält
```

## Im Viewer {#in-the-viewer}

1. Öffne den Viewer, wähle die `.3dheat`-Datei (**One file…**), dann **Load**.
2. Die Heatmap aller Spieler erscheint. Ist das Level der Karte einmal geladen
   (erstellt vom eigenen Werkzeug [3DHeat R6 Maps](https://github.com/Holdi601/3DHeat-Ext-R6-Maps)),
   legt der Viewer es von selbst unter das Match.
3. Der Reiter **Match** zeigt die Runden, Kills und die Anzeigetafel; die
   Wiedergabe spielt die Spieler als Figuren ab.

## Was in einem Match steckt {#what-is-in-a-match}

Position und Blickrichtung jedes Spielers (30-40 Mal pro Sekunde), Operator
und Ausrüstung, Drohnen und Gadgets, der Killfeed mit Waffen und Kopfschüssen,
jeder Platzierungs- und Entschärfungsversuch, Verstärkungen, die
Bombenstandorte, der Raum, in dem jeder Spieler ist, die Spuren, die Kugeln an
Wänden hinterlassen (mit dem Level-Objekt, auf dem sie sitzen), und das
Ergebnis jeder Runde. Die vollständige Liste der Spalten steht in der
[README](https://github.com/Holdi601/3DHeat-Ext-R6#columns).

## Schüsse, Fähigkeiten und Gadgets {#shots-abilities-and-gadgets}

Jede Nutzung dessen, was ein Spieler trägt, ist ein eigenes Ereignis, an der
Position des Spielers und mit dem Namen (`item`) und der Klasse (`itemClass`)
des Gegenstands:

| Ereignis | Wann |
|---|---|
| `shot` | Schüsse wurden abgegeben; `count` wie viele in diesem Moment, `left` die verbleibende Munition insgesamt |
| `reload` | ein Nachladen beginnt |
| `ability_use` | die Fähigkeit des Operators wird genutzt; `count` verbrauchte Ladungen, `left` verbleibende Ladungen |
| `gadget_deploy` | ein Gadget wird geworfen oder platziert, oder eine Drohne geht hinaus |
| `gadget_destroyed` | ein platziertes oder geworfenes Gadget ist verbraucht, ausgelöst oder zerstört |
| `gadget_pickup` | ein platziertes Gadget wird wieder aufgehoben |

Wo sich das geworfene oder platzierte Objekt verfolgen lässt, geben
`placedX`, `placedY`, `placedZ` an, wo es zur Ruhe kam, und die eigene Spur
des Gadgets ist nach ihm benannt.

Haltung (Hocken, Liegen) und Lehnen stehen noch nicht in den Tabellen.

Eine Aufnahme eines Spielers (nicht eines Zuschauers) enthält unter Umständen
nur, was dem Spiel dieses Spielers mitgeteilt wurde: Gegner außer Sicht können
fehlen.
