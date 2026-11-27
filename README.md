# ThermoPilot

Custom Home Assistant-integration til indsamling af varmepumpe- og bygningsdata og udvikling af en eksperimentel varmebehovsmodel.

> **Udviklingsversion 0.1.5:** Denne version er kun til overvågning og test. Den styrer ikke varmepumpen.

## Installation via HACS

1. Åbn **HACS → Integrationer** i Home Assistant.
2. Åbn menuen med de tre prikker, og vælg **Custom repositories**.
3. Indsæt `https://github.com/Frederik9078/HA-ThermoPilot` og vælg kategorien **Integration**.
4. Find **ThermoPilot**, og vælg Download.
5. Genstart Home Assistant.
6. Tilføj **ThermoPilot** under **Indstillinger → Enheder og tjenester → Tilføj integration**.

## Funktioner i version 0.1.5

- Læser en kumulativ energisensor i Wh, kWh eller MWh og beregner dagens forbrug ud fra tællerens ændring.
- Læser udetemperatur, fremløb og retur. Rumtemperaturer hentes automatisk fra de valgte climate-termostater.
- Beregner gennemsnitlig rumtemperatur ud fra climate-termostaternes aktuelle temperatur.
- Vælg rummenes eksisterende `climate`-termostater én gang; der kræves ingen separat rumtemperaturvælger. ThermoPilot læser både setpunkt (`temperature`) og aktuel temperatur (`current_temperature`).
- Beregner temperaturunderskud og lærer opvarmningshastighed pr. rum/kreds.
- Bruger `hvac_action` når det findes, ellers temperaturforskellen, til at vurdere om rummet kalder på varme.
- Estimerer resterende opvarmningstid ud fra hvert rums målte temperaturstigning.
- Beregner en 30-dages modelnøjagtighed ved historisk backtest: hver dags forbrug forudsiges kun ud fra tidligere afsluttede dage.
- Viser brugt energi i dag og en foreløbig prognose for elforbruget de næste 24 timer.
- Tomme valgfrie entitetsfelter og tomme telestat-/termostatlister håndteres ved lagring.
- Gemmer daglige datapunkter lokalt i Home Assistant.
- Efter mindst fem afsluttede dage tilpasser den en adaptiv, recency-vægtet model: samlet dagligt elforbrug = vejrafhængigt forbrug + grundlast. Nye dage vægtes højere, men målinger fra omtrent samme kalenderperiode i tidligere år får også ekstra sæsonvægt. Der gemmes op til 730 dage (ca. to år), så modellen kan genbruge erfaring fra samme årstid.

## 24-timers prognose

Sensoren **Forventet elforbrug næste 24 timer** bruger den adaptive døgnmodel og den senest målte udetemperatur som proxy for gennemsnitstemperaturen i den kommende periode. Det er en foreløbig prognose og ikke en egentlig vejrprognosebaseret beregning. En vejrprognosekilde skal tilføjes, før modellen kan tage højde for forventede temperaturændringer gennem de næste 24 timer. Forbruget omfatter samme typer elforbrug som den valgte energimåler, herunder eventuelt varmtvandsproduktion og elpatron.

## Modelnøjagtighed

Sensoren **Prognosenøjagtighed – 30 dage** viser 100 % minus den gennemsnitlige absolutte procentafvigelse på op til de seneste 30 dage, hvor modellen kunne lave en historisk prognose. Hver testdag holdes ude af træningsdata, så modellen ikke får lov at kende dagens faktiske forbrug på forhånd. Beregningen bruger dog dagens målte gennemsnitlige udetemperatur. Den måler derfor modellens evne til at forudsige elforbruget ved kendt vejr – ikke den samlede præcision inklusive vejrudsigten. Sensoren er tom, indtil der er tilstrækkeligt historisk datagrundlag til at lave backtests.

## Vigtige begrænsninger

Integrationen kan ikke måle den leverede varmeeffekt eller beregne en korrekt COP, fordi der ikke er en flowmåler eller varmemåler på varmesiden.

Der er ikke længere nogen særskilt VVB-/brugsvandsfunktion eller VVB-elpatronsensor i integrationen. Bemærk dog, at hvis den valgte Shelly-måler også måler varmepumpens kompressor under varmtvandsproduktion, vil dette elforbrug fortsat indgå i det samlede energiforbrug. Den separate elpatron i varmtvandsbeholderen er heller ikke målt særskilt.

Sensorerne **Vejrafhængigt elforbrug i dag** og **Estimeret samlet elforbrug i dag** er eksperimentelle estimater fra den adaptive model. Den er ikke et isoleret mål for rumopvarmning eller leveret varme. Det samlede elforbrug kan påvirkes af varmtvandsproduktion, elpatrondrift, driftsændringer og interne/solmæssige varmetilskud.

## Dataopsamling

- Energimåleren skal være en stigende totalmåler, ikke en øjeblikkelig effektmåler i W.
- Dagens forbrug begynder ved integrationens første aflæsning. Forbrug før installationen rekonstrueres ikke.
- Daglige modeldata opbygges fremadrettet. CSV-filer importeres ikke automatisk i denne version.
- Modellen kræver mindst fem afsluttede dage og mindst tre forskellige niveauer af graddøgn. Den genberegnes løbende, når nye dagsdata gemmes. Historikken gemmes i op til 730 dage, og målinger fra samme periode i tidligere år får ekstra vægt.

## Sensorer

Som standard aktiveres de brugerrettede sensorer: brugt energi i dag, estimeret opvarmningstid, forventet elforbrug næste 24 timer, 30-dages prognosenøjagtighed og modelstatus. Måle- og hjælpesensorer oprettes fortsat, men er deaktiveret som standard og kan aktiveres manuelt i entitetsindstillingerne.

- Samlet energimåler og samlet elforbrug i dag
- Aktuel og gennemsnitlig udetemperatur
- Gennemsnitlig rumtemperatur og antal rum med tilgængelig temperatur fra climate-termostater
- Fremløb, retur og temperaturforskel
- Antal rumtermostater, der kalder på varme
- Samlet temperaturunderskud og estimeret opvarmningstid pr. rum/kreds
- Vejrafhængigt elforbrug og estimeret samlet elforbrug i dag
- Modelkoefficient, modelgrundlast, antal modeldage, modelstatus og 30-dages prognosenøjagtighed

## Opdateringer

Nye versioner udgives som GitHub Releases med versions-tags, f.eks. `v0.1.5`. Når en ny release er udgivet, kan HACS tilbyde den som opdatering. Se GitHub-repositoriet for versionshistorik og installationsvejledning.

## Projekt

[GitHub repository](https://github.com/Frederik9078/HA-ThermoPilot)
