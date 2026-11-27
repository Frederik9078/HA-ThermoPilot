# ThermoPilot

Custom Home Assistant-integration til indsamling af varmepumpe- og bygningsdata og udvikling af en eksperimentel varmebehovsmodel.

> **Udviklingsversion 0.1.0:** Denne version er kun til overvågning og test. Den styrer ikke varmepumpen.

## Installation via HACS

1. Åbn **HACS → Integrationer** i Home Assistant.
2. Åbn menuen med de tre prikker, og vælg **Custom repositories**.
3. Indsæt `https://github.com/Frederik9078/HA-ThermoPilot` og vælg kategorien **Integration**.
4. Find **ThermoPilot**, og vælg Download.
5. Genstart Home Assistant.
6. Tilføj **ThermoPilot** under **Indstillinger → Enheder og tjenester → Tilføj integration**.

## Funktioner i version 0.1.0

- Læser en kumulativ energisensor i Wh, kWh eller MWh og beregner dagens forbrug ud fra tællerens ændring.
- Læser udetemperatur, fremløb, retur og valgfri rumtemperaturer.
- Beregner gennemsnit af de valgte rumtemperaturer.
- Kan tælle termostater, der aktuelt står `on`, `heat`, `heating`, `open`, `true` eller `1`.
- Termostat-/telestatvælgeren accepterer entiteter fra domænerne `sensor`, `binary_sensor`, `switch` og `climate`.
- Tomme valgfrie entitetsfelter og tomme telestat-/termostatlister håndteres ved lagring.
- Gemmer daglige datapunkter lokalt i Home Assistant.
- Efter mindst fem afsluttede dage tilpasser den en adaptiv, recency-vægtet model: samlet dagligt elforbrug = vejrafhængigt forbrug + grundlast. Nye dage vægtes højere end ældre observationer (14 dages halveringstid), så modellen gradvist følger ændringer i bygningens forbrug.

## Vigtige begrænsninger

Integrationen kan ikke måle den leverede varmeeffekt eller beregne en korrekt COP, fordi der ikke er en flowmåler eller varmemåler på varmesiden.

Der er ikke længere nogen særskilt VVB-/brugsvandsfunktion eller VVB-elpatronsensor i integrationen. Bemærk dog, at hvis den valgte Shelly-måler også måler varmepumpens kompressor under varmtvandsproduktion, vil dette elforbrug fortsat indgå i det samlede energiforbrug. Den separate elpatron i varmtvandsbeholderen er heller ikke målt særskilt.

Sensorerne **Vejrafhængigt elforbrug i dag** og **Estimeret samlet elforbrug i dag** er eksperimentelle estimater fra den adaptive model. Den er ikke et isoleret mål for rumopvarmning eller leveret varme. Det samlede elforbrug kan påvirkes af varmtvandsproduktion, elpatrondrift, driftsændringer og interne/solmæssige varmetilskud.

## Dataopsamling

- Energimåleren skal være en stigende totalmåler, ikke en øjeblikkelig effektmåler i W.
- Dagens forbrug begynder ved integrationens første aflæsning. Forbrug før installationen rekonstrueres ikke.
- Daglige modeldata opbygges fremadrettet. CSV-filer importeres ikke automatisk i denne version.
- Modellen kræver mindst fem afsluttede dage og mindst tre forskellige niveauer af graddøgn. Den genberegnes løbende, når nye dagsdata gemmes, og vægter de seneste 14 dage højest.

## Sensorer

- Samlet energimåler og samlet elforbrug i dag
- Aktuel og gennemsnitlig udetemperatur
- Gennemsnitlig rumtemperatur og antal aktive rumfølere
- Fremløb, retur og temperaturforskel
- Antal aktive termostater
- Vejrafhængigt elforbrug og estimeret samlet elforbrug i dag
- Modelkoefficient, modelgrundlast, antal modeldage og modelstatus

## Opdateringer

Nye versioner udgives som GitHub Releases med versions-tags, f.eks. `v0.1.0`. Når en ny release er udgivet, kan HACS tilbyde den som opdatering. Se GitHub-repositoriet for versionshistorik og installationsvejledning.

## Projekt

[GitHub repository](https://github.com/Frederik9078/HA-ThermoPilot)
