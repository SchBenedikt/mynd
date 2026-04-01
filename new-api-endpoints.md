# Deutscher Wetterdienst

Deutscher Wetterdienst: API
 1.2.0 
OAS3
openapi.yaml
API des Deutschen Wetterdienstes (DWD) aus der DWD App.

Neben unterschiedlichen Wetterwarnungen (s.u.) lassen sich unter /dwd.api.proxy.bund.dev/v30/stationOverviewExtended nach Angabe des Parameters stationIDs (z.B. 'G005') auch die Wetterdaten ausgewählter Wetterstationen anfordern (wobei die sog. 'Stationskennung' des DWD anzugeben ist).

Unter https://opendata.dwd.de/ bietet der DWD darüber hinaus auch aktuelle und historische Daten zu diversen Wetter- und Klimaphänomenen zum Download an (vgl. hierzu die offizielle Dokumentation hier). In diesem Zusammenhang erwähnenswert ist auch eine weitere offizielle Liste aller Wetterstationen (ohne Stationskennung aber mit sog. 'Stations_id') hier.

Ausführlichere Dokumentation
Servers

default


GET
​/stationOverviewExtended
Wetterstation Daten

GET
​/crowd_meldungen_overview_v2.json
DWD Crowdwettermeldungen

GET
​/warnings_nowcast.json
Nowcast Warnungen (deutsch)

GET
​/warnings_nowcast_en.json
Nowcast Warnungen (englisch)

GET
​/gemeinde_warnings_v2.json
Gemeinde Unwetterwarnungen (Deutsch)

GET
​/gemeinde_warnings_v2_en.json
Gemeinde Unwetterwarnungen (Englisch)

GET
​/warnings_coast.json
Küsten Unwetterwarnungen (deutsch)

GET
​/warnings_coast_en.json
Küsten Unwetterwarnungen (englisch)

GET
​/sea_warning_text.json
Hochsee Unwetterwarnungen als Text

GET
​/alpen_forecast_text_dwms.json
Alpen Wettervorhersage als Text

GET
​/warnings_lawine.json
Alpen Wettervorhersage als Text

Schemas
WarningNowcast
StationOverview
CROWDMeldung
GemeindeWarnings
Error
WarningCoast

# NINA Warnungen

Bundesamt für Bevölkerungsschutz: NINA API
 1.0.0 
OAS3
openapi.yaml
Erhalten Sie wichtige Warnmeldungen des Bevölkerungsschutzes für Gefahrenlagen wie zum Beispiel Gefahrstoffausbreitung oder Unwetter per Programmierschnittstelle.

the developer - Website
Servers

Warnings


GET
​/dashboard​/{ARS}.json
Meldungsübersicht nach ARS

GET
​/warnings​/{identifier}.json
Detailinformation zu einer Warnung

GET
​/warnings​/{identifier}.geojson
GeoJSON informationen zu einer Warnung.

GET
​/katwarn​/mapData.json
Katwarn Meldungen

GET
​/biwapp​/mapData.json
Biwapp Meldungen

GET
​/mowas​/mapData.json
Mowas Meldungen

GET
​/dwd​/mapData.json
Unwetterwarnungen des Deutschen Wetterdienstes

GET
​/lhp​/mapData.json
Meldungen des Länderübergreifenden Hochwasserportals

GET
​/police​/mapData.json
Polizeimeldungen

GET
​/mowas​/rss​/{ARS}.rss
MoWaS Meldungen als RSS-Feed
Covid


GET
​/appdata​/covid​/covidrules​/DE​/{ARS}.json
Corona Regelungen nach ARS

GET
​/appdata​/covid​/covidinfos​/DE​/covidinfos.json
Allgemeine Informationen zu Corona

GET
​/appdata​/covid​/covidticker​/DE​/covidticker.json
Covid-Ticker

GET
​/appdata​/covid​/covidticker​/DE​/tickermeldungen​/{id}.json
Detailinformationen zu Covid-Ticker Meldungen

GET
​/appdata​/covid​/covidmap​/DE​/covidmap.json
Kartendaten für Corona-Fallzahlen.
default


GET
​/appdata​/gsb​/logos​/logos.json
Liefert Namen und Logos für Sender-IDs

GET
​/appdata​/gsb​/logos​/{filename}
Logo-Bilddateien.

GET
​/appdata​/gsb​/eventCodes​/eventCodes.json
Liefert Event Codes und Name der Bilddateien.

GET
​/appdata​/gsb​/eventCodes​/{filename}
Event Code Bilddateien.

GET
​/appdata​/gsb​/notfalltipps​/DE​/notfalltipps.json
Notfalltipps

GET
​/appdata​/gsb​/faqs​/DE​/faq.json
FAQs

GET
​/dynamic​/version​/dataVersion.json
Liefert die Versionsnummer.
Archive


GET
​/archive.mowas​/{identifier}-mapping.json
Gesammelter Verlauf einer MOWAS Warnung

GET
​/archive.mowas​/{identifier}.json
Abruf einer archivierten MOWAS Warnung

# Deutsche Autobahnen
Autobahn App API
 1.0.1 
OAS3
openapi.yaml
Was passiert auf Deutschlands Bundesstraßen? API für aktuelle Verwaltungsdaten zu Baustellen, Staus und Ladestationen. Außerdem Zugang zu Verkehrsüberwachungskameras und vielen weiteren Datensätzen.

Die Autobahn GmbH des Bundes - Website
Send email to Die Autobahn GmbH des Bundes
Weiterführende Dokumentation
Servers

default


GET
​/
Liste verfügbarer Autobahnen

GET
​/{roadId}​/services​/roadworks
Liste aktueller Baustellen

GET
​/details​/roadworks​/{roadworkId}
Details einer Baustelle

GET
​/{roadId}​/services​/webcam
Liste verfügbarer Webcams

GET
​/details​/webcam​/{webcamId}
Details einer Webcam

GET
​/{roadId}​/services​/parking_lorry
Liste verfügbarer Rastplätze

GET
​/details​/parking_lorry​/{lorryId}
Details eines Rastplatzes

GET
​/{roadId}​/services​/warning
Liste aktueller Verkehrsmeldungen

GET
​/details​/warning​/{warningId}
Details zu einer Verkehrsmeldung

GET
​/{roadId}​/services​/closure
Liste aktueller Sperrungen

GET
​/details​/closure​/{closureId}
Details zu einer Sperrung

GET
​/{roadId}​/services​/electric_charging_station
Liste aktueller Ladestationen

GET
​/details​/electric_charging_station​/{stationId}
Details zu einer Ladestation

# Dashboard Deutschland
Indikator	ids-value	Beispiel-URL
Importe und Exporte von Wasserstoff	tile_1654002158461	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1654002158461
Täglicher LKW-Maut-Fahrleistungsindex	tile_1667226778807	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1667226778807
Lkw-Maut-Fahrleistungsindex	tile_1667205800085	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1667205800085
Preisindex für Eigentumswohnungen nach Kreistypen	data_woh_preise_immobilien_hpi_wohnungen	www.dashboard-deutschland.de/api/tile/indicators?ids=data_woh_preise_immobilien_hpi_wohnungen
HCOB Einkaufsmanagerindex	tile_1667982123933	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1667982123933
Umsatz im Ausbaugewerbe	tile_1654070793733	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1654070793733
Kapazitätsauslastung im Baugewerbe	data_bau_kapazitaetsauslastung_bbsr	www.dashboard-deutschland.de/api/tile/indicators?ids=data_bau_kapazitaetsauslastung_bbsr
Weltmarktpreise für Weizen	tile_1654606920834	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1654606920834
Automobilindustrie	tile_1666960710868	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1666960710868
Entwicklung der Nominallöhne nach Quintilen	tile_1684316122432	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1684316122432
Entwicklung des deutschen Arbeitsmarktes anhand der LinkedIn Hiring Rate	tile_1673880739519	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1673880739519
Flugverkehr weltweit	tile_1667989324139	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1667989324139
Anzahl genehmigter Wohnungen im Neubau nach Gebäudeart	data_woh_baugenehmigungen_wohnungen	www.dashboard-deutschland.de/api/tile/indicators?ids=data_woh_baugenehmigungen_wohnungen
Verbrauch von Mineralölprodukten in Deutschland	tile_1663665588691	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1663665588691
Füllstand deutscher Erdgasspeicher	tile_1667227714015	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1667227714015
Fertiggestellte Neubauten nach überwiegend verwendeter Heizenergie	tile_1654000747086	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1654000747086
Genehmigte neu zu errichtende Wohngebäude mit ein und zwei Wohnungen nach überwiegend verwendeter Heizenergie	tile_1663665272454	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1663665272454
Auftragseingang im Bauhauptgewerbe	data_bau_auftragseingang	www.dashboard-deutschland.de/api/tile/indicators?ids=data_bau_auftragseingang
Energieverbrauch für Wohnen nach Anwendungsbereichen	tile_1651060108903	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1651060108903
ifo Geschäftsklima	tile_1667288019608	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1667288019608
Umsatz im Gastgewerbe	tile_1667810908930	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1667810908930
Genehmigte und fertiggestellte Wohnungen	tile_1678111428688	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1678111428688
Verbraucherpreisindex für Nettokaltmiete, Wohnungsnebenkosten und Haushaltsenergie	data_woh_bruttokaltmiete	www.dashboard-deutschland.de/api/tile/indicators?ids=data_woh_bruttokaltmiete
Stimmungsindikatoren Konsum	tile_1667983271066	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1667983271066
Gold- und Kupferpreis	data_preise_gold_kupfer	www.dashboard-deutschland.de/api/tile/indicators?ids=data_preise_gold_kupfer
Verschuldung der bedeutendsten Sondervermögen des Bundes	tile_1650977632272	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1650977632272
Verbraucherpreisindex für Nettokaltmiete nach Kreistypen	data_woh_nettokaltmiete	www.dashboard-deutschland.de/api/tile/indicators?ids=data_woh_nettokaltmiete
Umsatz in Branchen des Verarbeitenden Gewerbes	data_umsatz_ausgewaehlte_branchen	www.dashboard-deutschland.de/api/tile/indicators?ids=data_umsatz_ausgewaehlte_branchen
HWWI-Rohstoffpreisindex	tile_1667215458776	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1667215458776
Kassenmäßige Steuereinnahmen aus Gemeindesteuern	data_gemeindesteuern	www.dashboard-deutschland.de/api/tile/indicators?ids=data_gemeindesteuern
Umlaufrenditen Staats- und Unternehmensanleihen	data_staats_und_unt_anleihen	www.dashboard-deutschland.de/api/tile/indicators?ids=data_staats_und_unt_anleihen
Kassenmäßige Steuereinnahmen insgesamt und der Gemeinden/Gemeindeverbände	data_steuereinnahmen_insgesamt_gemeinden	www.dashboard-deutschland.de/api/tile/indicators?ids=data_steuereinnahmen_insgesamt_gemeinden
Dienstleistungsproduktion	tile_1667825347006	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1667825347006
ZEW Konjunkturausblick	tile_1667228531297	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1667228531297
Exporterwartungen und Containerumschlag	tile_1666962783823	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1666962783823
Passantenfrequenzindex	tile_1667982573430	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1667982573430
Flugverkehr Deutschland	tile_1667987544456	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1667987544456
Preisentwicklung für ausgewählte Baumaterialien	tile_1667308898055	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1667308898055
Baupreisindizes	data_bau_bauleistungspreise	www.dashboard-deutschland.de/api/tile/indicators?ids=data_bau_bauleistungspreise
Produktion im Produzierenden Gewerbe	tile_1667824915093	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1667824915093
Auftragseingang in Branchen des Verarbeitenden Gewerbes	data_auftragseingang_ausgewaehlte_branchen	www.dashboard-deutschland.de/api/tile/indicators?ids=data_auftragseingang_ausgewaehlte_branchen
ifo Produktionserwartungen	tile_1667289137702	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1667289137702
Auftragseingang im Verarbeitenden Gewerbe	tile_1667828024262	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1667828024262
Entwicklung der Nominallöhne nach Beschäftigungsart	tile_1684314533676	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1684314533676
Umsatz mit Maßnahmen zur Verbesserung der Energieeffizienz von Gebäuden	tile_1665656599909	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1665656599909
Umsatz mit Motorenkraftstoffen an Tankstellen	tile_1663667870377	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1663667870377
Arbeitslosigkeit und offene Stellen	tile_1666958835081	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1666958835081
Preisveränderung	tile_1668694599167	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1668694599167
Entwicklung ausgewählter Aggregate des Bruttoinlandsprodukts	tile_1667814729862	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1667814729862
Gasimporte nach Deutschland	tile_1667993866759	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1667993866759
Einzelhandelsumsatz	tile_1667460685909	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1667460685909
Kassenmäßige Steuereinnahmen aus Gemeinschaft-, Bundes- und Landessteuern	data_gemeinschaft_bundes_landessteuern	www.dashboard-deutschland.de/api/tile/indicators?ids=data_gemeinschaft_bundes_landessteuern
Außenhandelsbilanz	data_aussenhandelsbilanz	www.dashboard-deutschland.de/api/tile/indicators?ids=data_aussenhandelsbilanz
Verschuldung des Bundes inklusive Darlehensfinanzierung nach Restlaufzeiten	tile_1650978274644	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1650978274644
Stromverbrauch	tile_1667214343714	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1667214343714
Wohnfläche in genehmigten Neubauwohnungen	data_woh_baugenehmigungen_wohnflaeche	www.dashboard-deutschland.de/api/tile/indicators?ids=data_woh_baugenehmigungen_wohnflaeche
Energieverbrauch für Wohnen nach Energieträgern	data_woh_energieverbrauch_energietraeger	www.dashboard-deutschland.de/api/tile/indicators?ids=data_woh_energieverbrauch_energietraeger
Passantenfrequenzen: Veränderung in ausgewählten Großstädten	data_mobilitaet_hystreet	www.dashboard-deutschland.de/api/tile/indicators?ids=data_mobilitaet_hystreet
Bereinigte kassenmäßige Steuereinnahmen aus Gemeinschaft-, Bundes- und Landessteuern	data_einnahmen_gemeinschaft_bundes_landessteuern	www.dashboard-deutschland.de/api/tile/indicators?ids=data_einnahmen_gemeinschaft_bundes_landessteuern
Außenhandel	tile_1667830902757	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1667830902757
Ölpreis (Sorte Brent)	tile_1667995478843	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1667995478843
Energiepreisveränderung	tile_1667826504852	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1667826504852
Stimmungsindikatoren Arbeitsmarkt	data_iab_ifo_barometer	www.dashboard-deutschland.de/api/tile/indicators?ids=data_iab_ifo_barometer
Kraftstoffpreise an öffentlichen Tankstellen	tile_1667921381760	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1667921381760
Neue Hypothekenverträge	tile_1667817211258	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1667817211258
Anteil der Grünen Bundeswertpapiere an der Verschuldung des Bundes inklusive Darlehensfinanzierung	tile_1650979109395	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1650979109395
Kassenmäßige Steuereinnahmen von Bund und Ländern	data_steuereinnahmen_bund_laender	www.dashboard-deutschland.de/api/tile/indicators?ids=data_steuereinnahmen_bund_laender
Außenhandel mit ausgewählten Ländern	tile_1667832713510	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1667832713510
Entwicklung des deutschen Arbeitsmarktes anhand von Stellenausschreibungen auf Indeed	tile_1666961477511	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1666961477511
Entwicklung des Bruttoinlandsprodukts	tile_1667811574092	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1667811574092
Baltic Dry Index	tile_1666960424161	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1666960424161
Außenhandel mit ausgewählten Ländergruppen	data_aussenhandel_laendergruppen	www.dashboard-deutschland.de/api/tile/indicators?ids=data_aussenhandel_laendergruppen
Verschuldung des Bundeshaushalts und seiner Sondervermögen	tile_1650978797816	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1650978797816
Produktion von Solarkollektoren, Solarmodulen und Wärmepumpen	tile_1663667563512	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1663667563512
Wechselkurs Euro/US-Dollar	tile_1667217389888	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1667217389888
Anzahl der genehmigten Wohnungen nach Bauherr	data_woh_baugenehmigungen_bautraeger	www.dashboard-deutschland.de/api/tile/indicators?ids=data_woh_baugenehmigungen_bautraeger
Kreditvergaben und Online-Transaktionen	tile_1667978809506	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1667978809506
Erwerbstätigkeit	tile_1667822587333	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1667822587333
Umsatz im Verarbeitenden Gewerbe	tile_1667828804581	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1667828804581
Benzinpreise im EU-Vergleich	tile_1663664545105	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1663664545105
ifo Knappheitsindikator	tile_1667289768923	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1667289768923
Renditespreads 10-jähriger Staatsanleihen gegenüber Deutschland	data_zinsspread_10_j_anleihen	www.dashboard-deutschland.de/api/tile/indicators?ids=data_zinsspread_10_j_anleihen
Strompreis	data_preise_strom	www.dashboard-deutschland.de/api/tile/indicators?ids=data_preise_strom
Wöchentlicher Aktivitätsindex	tile_1667211885741	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1667211885741
Beschäftigung im Baugewerbe	data_bau_beschaeftigung_vgr	www.dashboard-deutschland.de/api/tile/indicators?ids=data_bau_beschaeftigung_vgr
DIW Konjunkturbarometer	tile_1666961011248	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1666961011248
Preisindex für Ein- und Zweifamilienhäuser nach Kreistypen	data_woh_preise_immobilien_hpi_haueser	www.dashboard-deutschland.de/api/tile/indicators?ids=data_woh_preise_immobilien_hpi_haueser
Produktion in Branchen des Produzierenden Gewerbes	data_produktion_ausgewaehlte_branchen	www.dashboard-deutschland.de/api/tile/indicators?ids=data_produktion_ausgewaehlte_branchen
Pegelstände am Rhein	tile_1666960227357	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1666960227357
Preisentwicklung für Energie (Strom, Gas und andere Brennstoffe) im EU-Vergleich	tile_1663666887687	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1663666887687
Produktion im Baugewerbe	tile_1667890765659	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1667890765659
Energieverbrauch der Industrie nach Energieträgern	tile_1654002609295	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1654002609295
Nettostromerzeugung	tile_1666961555651	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1666961555651
Neuzulassungen von Personenkraftwagen nach Antriebsarten	tile_1663666467966	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1663666467966
Umsatz im Bauhauptgewerbe	tile_1654068021178	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1654068021178
Tischreservierungen über OpenTable	tile_1667208064878	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1667208064878
Exporte und Importe von Wärmepumpen und Photovoltaikanlagen	tile_1663664931250	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1663664931250
Renditen Bundeswertpapiere	data_umlaufrenditen_bundesanleihen	www.dashboard-deutschland.de/api/tile/indicators?ids=data_umlaufrenditen_bundesanleihen
Importe fossiler Energieträger	tile_1654001211812	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1654001211812
Bonitätschecks von Wohnungssuchenden	tile_1667995046610	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1667995046610
Preisindizes zu Bau oder Erwerb von Wohneigentum	tile_1656076602735	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1656076602735
Absatz von Warengruppen im Lebensmitteleinzelhandel	tile_1667821076015	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1667821076015
Außenhandel nach VGR-Konzept	tile_1667821569597	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1667821569597
Aktienindizes	tile_1667210963256	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1667210963256
Nettonennleistung der Anlagen zur Elektrizitätserzeugung	tile_1722432860129	www.dashboard-deutschland.de/api/tile/indicators?ids=tile_1722432860129

und 

Dashboard Deutschland API
 1.0.0 
OAS3
openapi.yaml
Auf https://www.dashboard-deutschland.de bietet das Statistische Bundesamt DESTATIS einen Überblick zu gesellschaftlich und wirtschaftlich relevanten Daten aus unterschiedlichen Themenbereichen. Diese werden durch Grafiken und Texte ergänzt und regelmäßig aktualisiert. Damit soll eine Möglichkeit geboten werden, aktuelle Kennzahlen und deren Entwicklung übersichtlich darzustellen.

Andreas Fischer - Website
Send email to Andreas Fischer
Servers

Get


GET
​/api​/dashboard​/get
Zugriff auf alle gültigen Einträge des id-Parameters
Indicators


GET
​/api​/tile​/indicators
Zugriff auf unterschiedliche Indikatoren
Geo


GET
​/geojson​/de-all.geo.json
Zugriff auf Geojson-Daten zu Deutschland und den Ländern


# Deutschland Atlas API

title	snippet	url	x
Basemap_light	Basemap_light	https://www.karto365.de/hosting/rest/services/Basemap_light/MapServer	
erw_mini_HA2023	Anteil der ausschließlich geringfügig entlohnten Beschäftigten am Arbeitsort an allen Erwerbstätigen im Jahr 2021 in _%	https://www.karto365.de/hosting/rest/services/erw_mini_HA2023/MapServer	erw_mini
pendel_b_HA2023	Durchschnittliche Pendeldistanzen aller SV_Beschäftigten am Wohnort 2021 in km	https://www.karto365.de/hosting/rest/services/pendel_b_HA2023/MapServer	pendel
p_nelade_r_HA2023	Pkw_Fahrzeit zur nächsten öffentlich zugänglichen Normalladestation für Elektroautos im Jahr 2023 in Minuten	https://www.karto365.de/hosting/rest/services/p_nelade_r_HA2023/MapServer	
pendel_a_HA2023	Pendlerverflechtungen zwischen Gemeindeverbänden nach Anzahl der Pendler im Jahr 2021	https://www.karto365.de/hosting/rest/services/pendel_a_HA2023/MapServer	Pendler202
heiz_wohn_HA2023	Anteil fertiggestellter Wohnungen mit primär erneuerbarer Heizenergie an allen errichteten Wohnungen in neuen Wohngebäuden im Jahr 2021 in _%	https://www.karto365.de/hosting/rest/services/heiz_wohn_HA2023/MapServer	heiz_wohn
teilz_w_HA2023	Weibliche sozialversicherungspflichtig Beschäftigte in Teilzeit am Arbeitsort an den weiblichen sozialversicherungspflichtig Beschäftigten im Jahr 2022 in _%	https://www.karto365.de/hosting/rest/services/teilz_w_HA2023/MapServer	teilz_w
p_freibad_HA2022	Pkw_Fahrzeit zum nächsten Freibad oder Naturbad im Jahr 2020 in Minuten	https://www.karto365.de/hosting/rest/services/p_freibad_HA2022/MapServer	p_freibad
preis_miet_HA2023	Wiedervermietungsmieten Angebotsmieten nettokalt im Jahr 2022 in € je m²	https://www.karto365.de/hosting/rest/services/preis_miet_HA2023/MapServer	
wohn_EFZH_HA2023	Fertiggestellte Wohnungen in neuen Ein_ und Zweifamilienhäusern je 10_000 Einwohner__innen im Jahr 2021	https://www.karto365.de/hosting/rest/services/wohn_EFZH_HA2023/MapServer	wohn_EZFH
bev_ausl_HA2023	Anteil der Ausländer__innen an der Gesamtbevölkerung im Jahr 2021 in _%	https://www.karto365.de/hosting/rest/services/bev_ausl_HA2023/MapServer	bev_ausl
bev_u18_HA2023	Anteil der unter 18_Jährigen an der Gesamtbevölkerung im Jahr 2021 in _%	https://www.karto365.de/hosting/rest/services/bev_u18_HA2023/MapServer	bev_u18
schule_oabschl_HA2023	Anteil der Schulabgänger__innen ohne Hauptschulabschluss an allen Schulabgänger__innen allgemeinbildender Schulen im Jahr 2021 in _%	https://www.karto365.de/hosting/rest/services/schule_oabschl_HA2023/MapServer	schule_oabschl
oenv_HA2023	Anteil der Bevölkerung_ die in maximal 600 m bzw_ bei Bahnhöfen 1_200 m Luftlinienentfernung um eine Haltestelle mit mindestens 20 Abfahrten im ÖV am Tag wohnt_ im Jahr 2022 in _%	https://www.karto365.de/hosting/rest/services/oenv_HA2023/MapServer	oenv
erw_minineben_HA2023	Anteil der geringfügig entlohnten Beschäftigten im Nebenjob am Arbeitsort an allen Erwerbstätigen im Jahr 2021 in _%	https://www.karto365.de/hosting/rest/services/erw_minineben_HA2023/MapServer	erw_minineben
teilz_m_HA2022	Männliche sozialversicherungspflichtig Beschäftigte in Teilzeit am Arbeitsort an den männlichen sozialversicherungspflichtig Beschäftigten im Jahr 2021 in _	https://www.karto365.de/hosting/rest/services/teilz_m_HA2022/MapServer	teilz_m
beschq_m_HA2023	Sozialversicherungspflichtig beschäftigte Männer am Wohnort je 100 Männer im erwerbsfähigen Alter im Jahr 2022	https://www.karto365.de/hosting/rest/services/beschq_m_HA2023/MapServer	beschq_m
p_kh_gru_b	Pkw_Fahrzeit zum nächsten Krankenhaus mit Grundversorgung im Jahr 2016 in Minuten, K33, p_kh_gru_b, feature	https://www.karto365.de/hosting/rest/services/p_kh_gru_b/MapServer	
st_einnkr_HA2021	Steuereinnahmekraft je Einwohner__in im Jahr 2018 in €; st_einnkr_HA2021	https://www.karto365.de/hosting/rest/services/st_einnkr_HA2021/MapServer	st_einnkr
fl_suv_HA2022	Anteil der Siedlungs_ und Verkehrsfläche an der Gesamtfläche im Jahr 2020 in _	https://www.karto365.de/hosting/rest/services/fl_suv_HA2022/MapServer	fl_suv
kbetr_u3_ZA2022	Anteil der betreuten Kinder unter 3 Jahren in Kindertageseinrichtungen__tagespflege an der Altersgruppe im Jahr 2020 in _	https://www.karto365.de/hosting/rest/services/kbetr_u3_ZA2022/MapServer	kbetr_u3
p_elade_HA2022	Pkw_Fahrzeit zur nächsten Ladestation für Elektroautos im Jahr 2020 in Minuten	https://www.karto365.de/hosting/rest/services/p_elade_HA2022/MapServer	p_elade
fl_suv_ZA2023	Anteil der Siedlungs_ und Verkehrsfläche an der Gesamtfläche im Jahr 2021 in _%	https://www.karto365.de/hosting/rest/services/fl_suv_ZA2023/MapServer	fl_suv
ko_kasskred_HA2022	Kommunale Kassenkredite je Einwohner__in im Jahr 2020 in €	https://www.karto365.de/hosting/rest/services/ko_kasskred_HA2022/MapServer	ko_kasskred
alq_HA2023	Arbeitslosenquote bezogen auf alle zivilen Erwerbspersonen im Jahr 2022 in _%	https://www.karto365.de/hosting/rest/services/alq_HA2023/MapServer	alq
p_markt_b	p_markt_b, feature	https://www.karto365.de/hosting/rest/services/p_markt_b/MapServer	
v_breitb1000_HA2023	Anteil der Haushalte_ die mit einer Internetgeschwindigkeit von ≥ 1_000 Mbit_s versorgt werden können_ im Juni 2022 in _%	https://www.karto365.de/hosting/rest/services/v_breitb1000_HA2023/MapServer	v_breitb1000
erw_vol_HA2023	Veränderung des Arbeitsvolumens am Arbeitsort 2014 zu 2020 in _%	https://www.karto365.de/hosting/rest/services/erw_vol_HA2023/MapServer	erw_vol
v_harzt_HA2023	Hausärzte__ärztinnen je 100_000 Einwohner__innen im Jahr 2020	https://www.karto365.de/hosting/rest/services/v_harzt_HA2023/MapServer	v_harzt
fl_landw_HA2022	Anteil der Landwirtschaftsfläche an der Gesamtfläche im Jahr 2020 in _	https://www.karto365.de/hosting/rest/services/fl_landw_HA2022/MapServer	fl_landw
pfl_stat_wms	Anteil der Pflegebedürftigen in stationärer Pflege im Jahr 2019 an den Pflegebedürftigen insgesamt in _	https://www.karto365.de/hosting/rest/services/pfl_stat_wms/MapServer	pfl_stat
bev_ausw_HA2022	Saldo der Außenwanderungen pro 10_000 Einwohner__innen im Jahr 2020	https://www.karto365.de/hosting/rest/services/bev_ausw_HA2022/MapServer	bev_ausw
kinder_bg_HA2022	Anteil der unter 15_Jährigen in SGB_II_Bedarfsgemeinschaften an der Altersgruppe im Jahr 2020 in _	https://www.karto365.de/hosting/rest/services/kinder_bg_HA2022/MapServer	kinder_bg
teilz_w_HA2022	Weibliche sozialversicherungspflichtig Beschäftigte in Teilzeit am Arbeitsort an den weiblichen sozialversicherungspflichtig Beschäftigten im Jahr 2021 in _	https://www.karto365.de/hosting/rest/services/teilz_w_HA2022/MapServer	teilz_w
VG250_Verbandsgemeinden1219_Punkt	VG250_Verbandsgemeinden1219_Punkt,	https://www.karto365.de/hosting/rest/services/VG250_Verbandsgemeinden1219_Punkt/MapServer	
bquali_oabschl_HA2022	Anteil sozialversicherungspflichtig Beschäftigter am Arbeitsort ohne einen Berufs__ akademischen Abschluss an allen sozialversicherungspflichtig Beschäftigten im Jahr 2021 in _	https://www.karto365.de/hosting/rest/services/bquali_oabschl_HA2022/MapServer	bquali_oabschl
elterng_v_HA2022	Anteil der Kinder_ deren Vater Elterngeld bezogen hat_ an allen anspruchsbegründeten Kindern im Jahr 2018 in _	https://www.karto365.de/hosting/rest/services/elterng_v_HA2022/MapServer	elterng_v
v_lte_ZA2022	Mobile Breitbandverfügbarkeit mit LTE ab 2 Mbit_s in _ der Fläche im Jahr 2021	https://www.karto365.de/hosting/rest/services/v_lte_ZA2022/MapServer	v_lte
kbetr_u3_HA2023	Anteil der betreuten Kinder unter 3 Jahren in Kindertageseinrichtungen__tagespflege an der Altersgruppe im Jahr 2021 in _%	https://www.karto365.de/hosting/rest/services/kbetr_u3_HA2023/MapServer	kbetr_u3
pendel_a_HA2021	Durchschnittliche Pendeldistanzen aller SV_Beschäftigten am Wohnort 2019 in km, pendel_a_HA2021	https://www.karto365.de/hosting/rest/services/pendel_a_HA2021/MapServer	pendel
p_hbad_HA2022	Pkw_Fahrzeit zum nächsten Hallenbad im Jahr 2020 in Minuten	https://www.karto365.de/hosting/rest/services/p_hbad_HA2022/MapServer	p_hbad
p_nelade_f_HA2023	Mittlere Pkw_Fahrzeit zur nächsten öffentlich zugänglichen Normalladestation für Elektroautos im Jahr 2023	https://www.karto365.de/hosting/rest/services/p_nelade_f_HA2023/MapServer	
VG250_Gemeinden1220_Punkt	VG250_Gemeinden1220_Punkt, feature to point, dann nur punktlayer beschriftet	https://www.karto365.de/hosting/rest/services/VG250_Gemeinden1220_Punkt/MapServer	
erw_vol_HA2022	Veränderung des Arbeitsvolumens am Arbeitsort 2014 zu 2019 in _	https://www.karto365.de/hosting/rest/services/erw_vol_HA2022/MapServer	erw_vol
ko_kasskred_HA2023	Kommunale Kassenkredite je Einwohner__in im Jahr 2021 in €	https://www.karto365.de/hosting/rest/services/ko_kasskred_HA2023/MapServer	ko_kasskred
sozsich_ZA2023	Anteil der Personen in sozialer Mindestsicherung an allen Einwohnerinnen und Einwohnern im Jahr 2020 in _%	https://www.karto365.de/hosting/rest/services/sozsich_ZA2023/MapServer	sozsich
teilz_insg_HA2022	Anteil der sozialversicherungspflichtig Beschäftigten in Teilzeit am Arbeitsort an den sozialversicherungspflichtig Beschäftigten im Jahr 2021 in _	https://www.karto365.de/hosting/rest/services/teilz_insg_HA2022/MapServer	teilz_insg
p_selade_r_HA2023	Pkw_Fahrzeit zur nächsten öffentlich zugänglichen Schnellladestation für Elektroautos im Jahr 2023 in Minuten	https://www.karto365.de/hosting/rest/services/p_selade_r_HA2023/MapServer	
VG250_Kreise1219_Punkt	tahoma 10 schwarz, zuerst features in punkte; Beste Platzierung 214	https://www.karto365.de/hosting/rest/services/VG250_Kreise1219_Punkt/MapServer	
v_breitb50_HA2021	Anteil der Haushalte, die mit einer Internetgeschwindigkeit von mindestens 1000 Mbit/s versorgt werden können im Jahr 2020 in %	https://www.karto365.de/hosting/rest/services/v_breitb50_HA2021/MapServer	v_breitb50
ko_kasskred_HA2021	Kommunale Kassenkredite je Einwohner__in im Jahr 2019 in €, ko_kasskred_HA2021	https://www.karto365.de/hosting/rest/services/ko_kasskred_HA2021/MapServer	ko_kasskred
schulden_HA2023	Anteil überschuldeter Personen über 18 Jahre an der Altersgruppe im Jahr 2022 in _%	https://www.karto365.de/hosting/rest/services/schulden_HA2023/MapServer	schulden
p_kh_sm_b	p_kh_sm_b, feature	https://www.karto365.de/hosting/rest/services/p_kh_sm_b/MapServer	
alq_HA2022_2	Arbeitslosenquote bezogen auf alle zivilen Erwerbspersonen im Jahr 2021 in _	https://www.karto365.de/hosting/rest/services/alq_HA2022_2/MapServer	alq
wohn_EZFH_ZA2022	Fertiggestellte Wohnungen in neuen Ein_ und Zweifamilienhäusern je 10_000 Einwohner__innen im Jahr 2020	https://www.karto365.de/hosting/rest/services/wohn_EZFH_ZA2022/MapServer	wohn_EZFH
wohn_leer_HA2021	Anteil leer stehender Wohnungen an allen Wohnungen 2018 in %, wohn_leer_HA2021	https://www.karto365.de/hosting/rest/services/wohn_leer_HA2021/MapServer	
kbetr_ue6_ZA2022	Anteil der betreuten Kinder ab 6 bis unter 11 Jahren in Kindertageseinrichtungen__tagespflege an der Altersgruppe im Jahr 2020 in _	https://www.karto365.de/hosting/rest/services/kbetr_ue6_ZA2022/MapServer	kbetr_ue6
kbetr_ue3_ZA2022	Anteil der betreuten Kinder ab 3 bis unter 6 Jahren in Kindertageseinrichtungen__tagespflege an der Altersgruppe im Jahr 2020 in _	https://www.karto365.de/hosting/rest/services/kbetr_ue3_ZA2022/MapServer	kbetr_ue3
elade_HA2022	Öffentlich zugängliche Ladepunkte für Elektrofahrzeuge im Jahr 2021 je 100_000 Einwohner__innen	https://www.karto365.de/hosting/rest/services/elade_HA2022/MapServer	elade
fl_wald_HA2022	Anteil der Waldfläche an der Gesamtfläche im Jahr 2020 in _	https://www.karto365.de/hosting/rest/services/fl_wald_HA2022/MapServer	fl_wald
teilz_w_HA2021	Weibliche sozialversicherungspflichtig Beschäftigte in Teilzeit am Arbeitsort je 100 weibliche Einwohner im erwerbsfähigen Alter im Jahr 2020, teilz_w_HA2021	https://www.karto365.de/hosting/rest/services/teilz_w_HA2021/MapServer	teilz_w
v_lte_wms	Mobile Breitbandverfügbarkeit mit LTE ab 2 Mbit_s in _ der Fläche im Jahr 2021	https://www.karto365.de/hosting/rest/services/v_lte_wms/MapServer	v_lte
bev_18_65_HA2023	Anteil der 18_ bis unter 65_Jährigen an der Gesamtbevölkerung im Jahr 2021 in _%	https://www.karto365.de/hosting/rest/services/bev_18_65_HA2023/MapServer	bev_18_65
bev_ausl_HA2021	Anteil der Ausländer__innen an der Gesamtbevölkerung im Jahr 2019 in %, bev_ausl_HA2021	https://www.karto365.de/hosting/rest/services/bev_ausl_HA2021/MapServer	bev_ausl
v_breitb50_HA2023	Anteil der Haushalte_ die mit einer Internetgeschwindigkeit von _ 50 Mbit_s versorgt werden können_ im Juni 2022 in _%	https://www.karto365.de/hosting/rest/services/v_breitb50_HA2023/MapServer	v_breitb50
erw_mini_ZA2022	Anteil der ausschließlich geringfügig entlohnten Beschäftigten am Arbeitsort an allen Erwerbstätigen im Jahr 2019 in _	https://www.karto365.de/hosting/rest/services/erw_mini_ZA2022/MapServer	erw_mini
kinder_bg_wms	Anteil der unter 15_Jährigen in SGB_II_Bedarfsgemeinschaften an der Altersgruppe im Jahr 2020 in _	https://www.karto365.de/hosting/rest/services/kinder_bg_wms/MapServer	kinder_bg
beschq_insg_HA2022	Sozialversicherungspflichtig Beschäftigte am Wohnort je 100 Einwohner__innen im erwerbsfähigen Alter im Jahr 2021	https://www.karto365.de/hosting/rest/services/beschq_insg_HA2022/MapServer	beschq_insg
preis_miet_HA2022	Wiedervermietungsmieten Angebotsmieten nettokalt im Jahr 2021 in € je m²	https://www.karto365.de/hosting/rest/services/preis_miet_HA2022/MapServer	
wahl_beteil_wms	Bundestagswahlbeteiligung 2021 in Kreisen in _	https://www.karto365.de/hosting/rest/services/wahl_beteil_wms/MapServer	wahl_beteil
bev_ue65_HA2021	Anteil der 65_Jährigen und Älteren an der Gesamtbevölkerung im Jahr 2019 in %, bev_ue65_HA2021	https://www.karto365.de/hosting/rest/services/bev_ue65_HA2021/MapServer	bev_ue65
beschq_m_HA2022	Sozialversicherungspflichtig beschäftigte Männer am Wohnort je 100 Männer im erwerbsfähigen Alter im Jahr 2021	https://www.karto365.de/hosting/rest/services/beschq_m_HA2022/MapServer	beschq_m
st_einnkr_ZA2023	Steuereinnahmekraft je Einwohner__in im Jahr 2021 in €	https://www.karto365.de/hosting/rest/services/st_einnkr_ZA2023/MapServer	st_einnkr
luftrtng_b	luftrtng, k36, feature	https://www.karto365.de/hosting/rest/services/luftrtng_b/MapServer	
einbr_HA2022	Fälle von Wohnungseinbruchdiebstahl pro 100_000 Einwohner__innen im Jahr 2021	https://www.karto365.de/hosting/rest/services/einbr_HA2022/MapServer	einbr
p_sek_1_a	Pkw_Fahrzeit zur nächsten Schule der Sekundarstufe I im Jahr 2015_16_17 in Minuten, K41, p_sek_1	https://www.karto365.de/hosting/rest/services/p_sek_1_a/MapServer	
erw_wachs_HA2023	Gemittelte Entwicklung der Erwerbstätigenzahl am Arbeitsort von 2011 bis 2021 pro Jahr in _%	https://www.karto365.de/hosting/rest/services/erw_wachs_HA2023/MapServer	erw_wachs
bev_ue65_HA2023	Anteil der 65_Jährigen und Älteren an der Gesamtbevölkerung im Jahr 2021 in _%	https://www.karto365.de/hosting/rest/services/bev_ue65_HA2023/MapServer	bev_ue65
p_apo_f_ZA2022	Pkw_Fahrzeit zum nächsten öffentlichen Apotheke im Jahr 2020 in Minuten	https://www.karto365.de/hosting/rest/services/p_apo_f_ZA2022/MapServer	
bev_entw_ZA2022	Gemittelte Entwicklung der Bevölkerungszahl zwischen 2015 und 2020 pro Jahr in _	https://www.karto365.de/hosting/rest/services/bev_entw_ZA2022/MapServer	bev_entw
wohn_MFH_ZA2022	Fertiggestellte Wohnungen in neuen Mehrfamilienhäusern je 10_000 Einwohner__innen im Jahr 2020	https://www.karto365.de/hosting/rest/services/wohn_MFH_ZA2022/MapServer	wohn_MFH
eauto_HA2022	Anteil von Pkw mit reinem Elektroantrieb BEV an allen Pkw im Jahr 2022 in _	https://www.karto365.de/hosting/rest/services/eauto_HA2022/MapServer	eauto
kinder_bg_HA2021	Anteil der unter 15_Jährigen in SGB_II_Bedarfsgemeinschaften an der Altersgruppe im Jahr 2019 in %, kinder_bg_HA2021	https://www.karto365.de/hosting/rest/services/kinder_bg_HA2021/MapServer	kinder_bg
bev_u18_HA2021	Anteil der unter 18_Jährigen an der Gesamtbevölkerung im Jahr 2019 in %, , bev_u18_HA2021	https://www.karto365.de/hosting/rest/services/bev_u18_HA2021/MapServer	bev_u18
schule_oabschl_HA2022	Anteil der Schulabgänger__innen ohne Hauptschulabschluss an allen Schulabgänger__innen allgemeinbildender Schulen im Jahr 2020 in _	https://www.karto365.de/hosting/rest/services/schule_oabschl_HA2022/MapServer	schule_oabschl
beschq_insg_HA2021	Sozialversicherungspflichtig Beschäftigte am Wohnort je 100 Einwohner__innen im erwerbsfähigen Alter im Jahr 2020; beschq_insg_HA2021	https://www.karto365.de/hosting/rest/services/beschq_insg_HA2021/MapServer	beschq_insg
v_harzt_HA2021	Hausärzte__ärztinnen im Jahr 2017 je 100_000 Einwohner__innen	https://www.karto365.de/hosting/rest/services/v_harzt_HA2021/MapServer	v_harzt
bev_ue65_ZA2022	Anteil der 65_Jährigen und Älteren an der Gesamtbevölkerung im Jahr 2020 in _	https://www.karto365.de/hosting/rest/services/bev_ue65_ZA2022/MapServer	bev_ue65
p_hbad_f_HA2022	feautre abfrage für p_hbad	https://www.karto365.de/hosting/rest/services/p_hbad_f_HA2022/MapServer	
VG250_GEM1217_neu	VG250_GEM1217_neu	https://www.karto365.de/hosting/rest/services/VG250_GEM1217_neu/MapServer	
kbetr_ue3_HA2023	Anteil der betreuten Kinder ab 3 bis unter 6 Jahren in Kindertageseinrichtungen_ _tagespflege an der Altersgruppe im Jahr 2021 in _%	https://www.karto365.de/hosting/rest/services/kbetr_ue3_HA2023/MapServer	kbetr_ue3
erw_mini_ZA2023	Anteil der ausschließlich geringfügig entlohnten Beschäftigten am Arbeitsort an allen Erwerbstätigen im Jahr 2020 in _%	https://www.karto365.de/hosting/rest/services/erw_mini_ZA2023/MapServer	erw_mini
grusi_ZA2022	Anteil der Bevölkerung mit Grundsicherung im Alter an den 65_Jährigen und Älteren im Jahr 2020 in _	https://www.karto365.de/hosting/rest/services/grusi_ZA2022/MapServer	grusi
wohn_MFH_HA2023	Fertiggestellte Wohnungen in neuen Mehrfamilienhäusern je 10_000 Einwohner__innen im Jahr 2021	https://www.karto365.de/hosting/rest/services/wohn_MFH_HA2023/MapServer	wohn_MFH
grusi_wms	Anteil der Bevölkerung mit Grundsicherung im Alter an den 65_Jährigen und Älteren im Jahr 2020 in _	https://www.karto365.de/hosting/rest/services/grusi_wms/MapServer	grusi
kbtr_pers_HA2021	Plätze in Kindertageseinrichtungen je pädagogisch tätige Person im Jahr 2019, kbtr_pers_HA2021	https://www.karto365.de/hosting/rest/services/kbtr_pers_HA2021/MapServer	kbtr_pers
VG250_Verbandsgemeinden_1220_Punkt	VG250_Verbandsgemeinden_1220_Punkt, feature to point, dann punktelaer beschriftet	https://www.karto365.de/hosting/rest/services/VG250_Verbandsgemeinden_1220_Punkt/MapServer	
wohn_EZFH_HA2021	Fertiggestellte Wohnungen in neuen Ein_ und Zweifamilienhäusern je 10_000 Einwohner__innen im Jahr 2019, wohn_EZFH_HA2021	https://www.karto365.de/hosting/rest/services/wohn_EZFH_HA2021/MapServer	wohn_EZFH
bev_binw_HA2022	Saldo der Binnenwanderungen pro 10_000 Einwohner__innen im Jahr 2020	https://www.karto365.de/hosting/rest/services/bev_binw_HA2022/MapServer	bev_binw
p_ozmz_oev_r_HA2021	Reisezeit mit dem Öffentlichen Verkehr ÖV zum Stadtzentrum des nächsten Ober_ oder Mittelzentrum 2020 in Minuten, p_ozmz_oev_r_HA2021, Raster	https://www.karto365.de/hosting/rest/services/p_ozmz_oev_r_HA2021/MapServer	
bquali_unifh_HA2022	Anteil sozialversicherungspflichtig Beschäftigter am Arbeitsort mit einem akademischen Abschluss an allen sozialversicherungspflichtig Beschäftigten im Jahr 2021 in _	https://www.karto365.de/hosting/rest/services/bquali_unifh_HA2022/MapServer	bquali_unifh
schulden_HA2022	Anteil überschuldeter Personen über 18 Jahre an der Altersgruppe im Jahr 2021 in _	https://www.karto365.de/hosting/rest/services/schulden_HA2022/MapServer	schulden
fl_landw_HA2021	Anteil der Landwirtschaftsfläche an der Gesamtfläche im Jahr 2019 in %, fl_landw_HA2021	https://www.karto365.de/hosting/rest/services/fl_landw_HA2021/MapServer	fl_landw
p_selade_f_HA2023	Mittlere Pkw_Fahrzeit zur nächsten öffentlich zugänglichen Schnellladestation für Elektroautos im Jahr 2023	https://www.karto365.de/hosting/rest/services/p_selade_f_HA2023/MapServer	
grusi_HA2023	Anteil der Bevölkerung mit Grundsicherung im Alter an den 65_Jährigen und Älteren im Jahr 2022 in _%	https://www.karto365.de/hosting/rest/services/grusi_HA2023/MapServer	grusi
VG250_Kreise_1221_Punkte	VG250_Kreise_1221_Punkte, Feature to Point, dann Punktelayer beschriftet	https://www.karto365.de/hosting/rest/services/VG250_Kreise_1221_Punkte/MapServer	
kbtr_pers_wms	Plätze in Kindertageseinrichtungen je pädagogisch tätige Person im Jahr 2021	https://www.karto365.de/hosting/rest/services/kbtr_pers_wms/MapServer	kbtr_pers
beschq_w_HA2022	Sozialversicherungspflichtig beschäftigte Frauen am Wohnort je 100 Frauen im erwerbsfähigen Alter im Jahr 2021	https://www.karto365.de/hosting/rest/services/beschq_w_HA2022/MapServer	beschq_w
erw_bip_HA2021	Bruttoinlandsprodukt je erwerbstätige Person im Jahr 2018 in 1_000 €, erw_bip_HA2021	https://www.karto365.de/hosting/rest/services/erw_bip_HA2021/MapServer	erw_bip
hh_veink_ZA2022	Verfügbares Einkommen privater Haushalte je Einwohner__in im Jahr 2019 in 1_000 €	https://www.karto365.de/hosting/rest/services/hh_veink_ZA2022/MapServer	hh_veink
bev_entw_HA2023	Gemittelte Entwicklung der Bevölkerungszahl zwischen 2016 und 2021 pro Jahr in _%	https://www.karto365.de/hosting/rest/services/bev_entw_HA2023/MapServer	bev_entw
beschq_w_HA2023	Sozialversicherungspflichtig beschäftigte Frauen am Wohnort je 100 Frauen im erwerbsfähigen Alter im Jahr 2022	https://www.karto365.de/hosting/rest/services/beschq_w_HA2023/MapServer	beschq_w
p_elade_f_HA2022	feature abfrage layer für p_elade	https://www.karto365.de/hosting/rest/services/p_elade_f_HA2022/MapServer	
bev_dicht_HA2023	Einwohner__innen je km² im Jahr 2021	https://www.karto365.de/hosting/rest/services/bev_dicht_HA2023/MapServer	bev_dicht
p_ozmz_miv_f_HA2021	p_ozmz_miv_f_HA2021, Feature	https://www.karto365.de/hosting/rest/services/p_ozmz_miv_f_HA2021/MapServer	
pfl_ambu_ZA2022	Anteil der Pflegebedürftigen in ambulanter Pflege an den Pflegebedürftigen insgesamt im Jahr 2019 in _	https://www.karto365.de/hosting/rest/services/pfl_ambu_ZA2022/MapServer	pfl_ambu
wohn_MFH_HA2021	Fertiggestellte Wohnungen in neuen Mehrfamilienhäusern je 10_000 Einwohner__innen im Jahr 2019, wohn_MFH_HA2021	https://www.karto365.de/hosting/rest/services/wohn_MFH_HA2021/MapServer	wohn_MFH
bev_entw_ZA2021	Gemittelte Entwicklung der Bevölkerungszahl zwischen 2014 und 2019 pro Jahr in %, k3, bev_entw_ZA2021	https://www.karto365.de/hosting/rest/services/bev_entw_ZA2021/MapServer	bev_entw
p_hbad_r_HA2022	Pkw_Fahrzeit zum nächsten Hallenband im Jahr 2020 in Minuten	https://www.karto365.de/hosting/rest/services/p_hbad_r_HA2022/MapServer	
wohn_EZFH_HA2023	Fertiggestellte Wohnungen in neuen Ein_ und Zweifamilienhäusern je 10_000 Einwohner__innen im Jahr 2021	https://www.karto365.de/hosting/rest/services/wohn_EZFH_HA2023/MapServer	wohn_EZFH
fl_suv_HA2021	Anteil der Siedlungs_ und Verkehrsfläche an der Gesamtfläche im Jahr 2019 in %, fl_suv_HA2021	https://www.karto365.de/hosting/rest/services/fl_suv_HA2021/MapServer	fl_suv
bquali_unifh_HA2021	Anteil sozialversicherungspflichtig Beschäftigter am Arbeitsort mit einem akademischen Abschluss an allen sozialversicherungspflichtig Beschäftigten im Jahr 2020 in %, bquali_unifh_HA2021	https://www.karto365.de/hosting/rest/services/bquali_unifh_HA2021/MapServer	bquali_unifh
luftrtng_a	Erreichbarkeit durch Luftrettung während des Tages im Jahr 2016 in Minuten, luftrtng, K36, Raster	https://www.karto365.de/hosting/rest/services/luftrtng_a/MapServer	
p_grunds_b	p_grunds_b, feature	https://www.karto365.de/hosting/rest/services/p_grunds_b/MapServer	
p_ozmz_miv_r_HA2021	Pkw_Fahrzeit zum Stadtzentrum des nächsten Ober_ oder Mittelzentrum 2020 in Minuten, p_ozmz_miv_r_HA2021, Raster	https://www.karto365.de/hosting/rest/services/p_ozmz_miv_r_HA2021/MapServer	
preis_miet_HA2021	Wiedervermietungsmieten in mittlerer_guter Wohnlage Angebotsmieten nettokalt 2020 in € je m², preis_miet_HA2021	https://www.karto365.de/hosting/rest/services/preis_miet_HA2021/MapServer	
p_poli_a	Pkw_Fahrzeit von der nächsten Polizeidienststelle im Jahr 2014 in Minuten, K50, p_poli_a	https://www.karto365.de/hosting/rest/services/p_poli_a/MapServer	
straft_HA2021	Straftaten insgesamt pro 100_000 Einwohner__innen im Jahr 2020, straft_HA2021	https://www.karto365.de/hosting/rest/services/straft_HA2021/MapServer	straft
bev_entw_wms	Gemittelte Entwicklung der Bevölkerungszahl zwischen 2015 und 2020 pro Jahr in _	https://www.karto365.de/hosting/rest/services/bev_entw_wms/MapServer	bev_entw
v_breitb50_HA2022	Anteil der Haushalte_ die mit einer Internetgeschwindigkeit von mindestens 50 Mbit_s versorgt werden können_ im Juni 2021 in _	https://www.karto365.de/hosting/rest/services/v_breitb50_HA2022/MapServer	v_breitb50
erw_minineben_ZA2023	Anteil der geringfügig entlohnten Beschäftigten im Nebenjob am Arbeitsort an allen Erwerbstätigen im Jahr 2020 in _&	https://www.karto365.de/hosting/rest/services/erw_minineben_ZA2023/MapServer	erw_minineben
alq_HA2022	Arbeitslosenquote bezogen auf alle zivilen Erwerbspersonen im Jahr 2021 in _	https://www.karto365.de/hosting/rest/services/alq_HA2022/MapServer	alq
p_harzt_b	K31, p_harzt_b, featureinfo	https://www.karto365.de/hosting/rest/services/p_harzt_b/MapServer	
heiz_wohn_HA2022	Anteil fertiggestellter Wohnungen mit primär erneuerbarer Heizenergie an allen errichteten Wohnungen in neuen Wohngebäuden im Jahr 2020 in _	https://www.karto365.de/hosting/rest/services/heiz_wohn_HA2022/MapServer	heiz_wohn
VG250_v_lte_Grenzen	VG250_v_lte_Grenzen	https://www.karto365.de/hosting/rest/services/VG250_v_lte_Grenzen/MapServer	
fl_wald_HA2021	Anteil der Waldfläche an der Gesamtfläche im Jahr 2019 in %, fl_wald_HA2021	https://www.karto365.de/hosting/rest/services/fl_wald_HA2021/MapServer	fl_wald
erw_vol_HA2021	Anteil der Pflegebedürftigen in ambulanter Pflege im Jahr 2017 an den Pflegebedürftigen insgesamt in _	https://www.karto365.de/hosting/rest/services/erw_vol_HA2021/MapServer	erw_vol
p_ozmz_b	Durchschnittliche bevölkerungsgewichtete Pkw-Fahrzeit zum Stadtzentrum des nächst_en Ober- oder Mittelzentrum 2019 in Minuten, K29, p_ozmz	https://www.karto365.de/hosting/rest/services/p_ozmz_b/MapServer	
kbetr_ue3_HA2021	Anteil der betreuten Kinder zwischen 3 und 6 Jahren in Kindertageseinrichtungen__tagespflege an der Altersgruppe im Jahr 2019 in _, kbetr_ue3_HA2021	https://www.karto365.de/hosting/rest/services/kbetr_ue3_HA2021/MapServer	kbetr_ue3
schule_oabschl_HA2021	Anteil der Schulabgänger__innen ohne Hauptschulabschluss an allen Schulabgänger__innen allgemeinbildender Schulen im Jahr 2019 in %, schule_oabschl_HA2021	https://www.karto365.de/hosting/rest/services/schule_oabschl_HA2021/MapServer	schule_oabschl
pfl_geld_ZA2022	Anteil der Pflegegeldempfänger__innen im Jahr 2019 an den Pflegebedürftigen insgesamt in _	https://www.karto365.de/hosting/rest/services/pfl_geld_ZA2022/MapServer	pfl_geld
erw_bip_ZA2023	Bruttoinlandsprodukt je erwerbstätige Person im Jahr 2020 in 1_000 €	https://www.karto365.de/hosting/rest/services/erw_bip_ZA2023/MapServer	erw_bip
p_apo_b	p_apo, feature	https://www.karto365.de/hosting/rest/services/p_apo_b/MapServer	
p_ozmz_oev_f_HA2021	p_ozmz_oev_f_HA2021, feature	https://www.karto365.de/hosting/rest/services/p_ozmz_oev_f_HA2021/MapServer	
kbetr_ue6_HA2021	Anteil der betreuten Kinder ab 6 bis unter 11 Jahren in Kindertageseinrichtungen__tagespflege an der Altersgruppe im Jahr 2019 in %, kbetr_ue6_HA2021	https://www.karto365.de/hosting/rest/services/kbetr_ue6_HA2021/MapServer	kbetr_ue6
teilz_m_HA2021	Männliche sozialversicherungspflichtig Beschäftigte in Teilzeit am Arbeitsort je 100 männliche Einwohner im erwerbsfähigen Alter im Jahr 2020, teilz_m_HA2021	https://www.karto365.de/hosting/rest/services/teilz_m_HA2021/MapServer	teilz_m
erw_wachs_ZA2023	Gemittelte Entwicklung der Erwerbstätigenzahl am Arbeitsort von 2010 bis 2020 pro Jahr in _	https://www.karto365.de/hosting/rest/services/erw_wachs_ZA2023/MapServer	erw_wachs
p_apo_a	Pkw_Fahrzeit zum nächsten öffentlichen Apotheke im Jahr 2013 in Minuten, K35, p_apo_a	https://www.karto365.de/hosting/rest/services/p_apo_a/MapServer	
sozsich_HA2021	Anteil der Personen in sozialer Mindestsicherung an allen Einwohnerinnen und Einwohnern im Jahr 2019 in %, sozsich_HA2021	https://www.karto365.de/hosting/rest/services/sozsich_HA2021/MapServer	sozsich
v_harzt_HA2022	Hausärzte__ärztinnen je 100_000 Einwohner__innen im Jahr 2019	https://www.karto365.de/hosting/rest/services/v_harzt_HA2022/MapServer	v_harzt
oenv_wms	Anteil der Bevölkerung_ die in maximal 600 m bzw_ bei Bahnhöfen 1_200 m Luftlinienentfernung um eine Haltestelle mit mindestens 20 Abfahrten im ÖV am Tag wohnt_ im Jahr 2020 in _	https://www.karto365.de/hosting/rest/services/oenv_wms/MapServer	oenv
wahl_beteil_HA2022	Bundestagswahlbeteiligung 2021 in Kreisen in _	https://www.karto365.de/hosting/rest/services/wahl_beteil_HA2022/MapServer	wahl_beteil
grusi_ZA2023	Anteil der Bevölkerung mit Grundsicherung im Alter an den 65_Jährigen und Älteren im Jahr 2021 in _	https://www.karto365.de/hosting/rest/services/grusi_ZA2023/MapServer	grusi
p_harzt_a	Pkw_Fahrzeit zur nächsten Hausärztin oder zum nächsten Hausarzt im Jahr 2016 in Minuten, K31, p_harzt_a	https://www.karto365.de/hosting/rest/services/p_harzt_a/MapServer	
kbtr_pers_ZA2022	Plätze in Kindertageseinrichtungen je pädagogisch tätige Person im Jahr 2021	https://www.karto365.de/hosting/rest/services/kbtr_pers_ZA2022/MapServer	kbtr_pers
schulden_HA2021	Anteil überschuldeter Personen über 18 Jahren an der Altersgruppe im Jahr 2020 in %, HA2021	https://www.karto365.de/hosting/rest/services/schulden_HA2021/MapServer	schulden
elterng_v_HA2021	Anteil der Kinder_ für die mindestens ein männlicher Leistungsbezieher Elterngeld erhalten hat_ an allen anspruchsbegründenden Kindern im Jahr 2017 in %, elterng_v_HA2021	https://www.karto365.de/hosting/rest/services/elterng_v_HA2021/MapServer	elterng_v
p_markt_a	Pkw_Fahrzeit zum nächsten Supermarkt oder Discounter im Jahr 2017 in Minuten, K30, p_markt	https://www.karto365.de/hosting/rest/services/p_markt_a/MapServer	
wahl_beteil	Bundestagswahlbeteiligung 2017 in Gemeinden in %, K10, wahl_beteil	https://www.karto365.de/hosting/rest/services/wahl_beteil/MapServer	wahl_beteil
bev_binw_HA2021	Saldo der Binnenwanderungen pro 10_000 Einwohner__innen im Jahr 2019; bev_binw_HA2021	https://www.karto365.de/hosting/rest/services/bev_binw_HA2021/MapServer	bev_binw
bev_ausl_ZA2022	Anteil der Ausländer__innen an der Gesamtbevölkerung im Jahr 2020 in _	https://www.karto365.de/hosting/rest/services/bev_ausl_ZA2022/MapServer	bev_ausl
hh_veink_ZA2023	Verfügbares Einkommen privater Haushalte je Einwohner__in im Jahr 2020 in 1_000 €	https://www.karto365.de/hosting/rest/services/hh_veink_ZA2023/MapServer	hh_veink
pfl_ambu_HA2021	Anteil der Pflegebedürftigen in ambulanter Pflege im Jahr 2017 an den Pflegebedürftigen insgesamt in %, pfl_ambu_HA2021	https://www.karto365.de/hosting/rest/services/pfl_ambu_HA2021/MapServer	pfl_ambu
erw_minineben_HA2021	Anteil der geringfügig entlohnten Beschäftigten im Nebenjob am Arbeitsort an allen Erwerbstätigen 2018 in %, erw_minineben_HA2021	https://www.karto365.de/hosting/rest/services/erw_minineben_HA2021/MapServer	erw_minineben
v_breitb1000_HA2021	Anteil der Haushalte, die mit einer Internetgeschwindigkeit von mindestens 1000 Mbit/s versorgt werden können im Jahr 2020 in %	https://www.karto365.de/hosting/rest/services/v_breitb1000_HA2021/MapServer	v_breitb1000
einbr_HA2021	Fälle von Wohnungseinbruchdiebstahl pro 100_000 Einwohner__innen im Jahr 2020, einbr_HA2021	https://www.karto365.de/hosting/rest/services/einbr_HA2021/MapServer	einbr
p_kh_gru_a	Pkw_Fahrzeit zum nächsten Krankenhaus mit Grundversorgung im Jahr 2016 in Minuten; K33, p_kh_gru	https://www.karto365.de/hosting/rest/services/p_kh_gru_a/MapServer	
pfl_stat_ZA2022	Anteil der Pflegebedürftigen in stationärer Pflege an den Pflegebedürftigen insgesamt im Jahr 2019 in _	https://www.karto365.de/hosting/rest/services/pfl_stat_ZA2022/MapServer	pfl_stat
teilz_insg_HA2021	Anteil der sozialversicherungspflichtig Beschäftigten in Teilzeit am Arbeitsort an den sozialversicherungspflichtig Beschäftigten im Jahr 2020 in %, teilz_insg_HA2021	https://www.karto365.de/hosting/rest/services/teilz_insg_HA2021/MapServer	teilz_insg
erw_mini_HA2021	Anteil der ausschließlich geringfügig entlohnten Beschäftigten am Arbeitsort an allen Erwerbstätigen 2018 in %, erw_mini_HA2021	https://www.karto365.de/hosting/rest/services/erw_mini_HA2021/MapServer	erw_mini
beschq_m_HA2021	Sozialversicherungspflichtig beschäftigte Männer am Wohnort je 100 Männer im erwerbsfähigen Alter im Jahr 2020, beschq_m_HA2021	https://www.karto365.de/hosting/rest/services/beschq_m_HA2021/MapServer	beschq_m
einbr_wms	Fälle von Wohnungseinbruchdiebstahl pro 100_000 Einwohner__innen im Jahr 2021	https://www.karto365.de/hosting/rest/services/einbr_wms/MapServer	einbr
pfl_geld_HA2021	Anteil der Pflegegeldempfänger__innen im Jahr 2017 an den Pflegebedürftigen insgesamt in _, pfl_geld_HA2021	https://www.karto365.de/hosting/rest/services/pfl_geld_HA2021/MapServer	pfl_geld
bev_u18_za2022	Anteil der unter 18_Jährigen an der Gesamtbevölkerung im Jahr 2020 in _	https://www.karto365.de/hosting/rest/services/bev_u18_za2022/MapServer	bev_u18
erw_minineben_ZA2022	Anteil der geringfügig entlohnten Beschäftigten im Nebenjob am Arbeitsort an allen Erwerbstätigen im Jahr 2019 in _	https://www.karto365.de/hosting/rest/services/erw_minineben_ZA2022/MapServer	erw_minineben
oenv_HA2021	Anteil der Bevölkerung_ die in maximal 600 m bzw_ bei Bahnhöfen 1_200 m Luftlinienentfernung um eine Haltestelle mit mindestens 20 Abfahrten im ÖV am Tag wohnt_ im Jahr 2020 in %, oenv_HA2021	https://www.karto365.de/hosting/rest/services/oenv_HA2021/MapServer	oenv
p_freibad_r_HA2022	Pkw_Fahrzeit zum nächsten Natur_ oder Freibad im Jahr 2020 in Minuten	https://www.karto365.de/hosting/rest/services/p_freibad_r_HA2022/MapServer	
p_freibad_f_HA2022	feature abfrage layer für p_freibad	https://www.karto365.de/hosting/rest/services/p_freibad_f_HA2022/MapServer	
elternv_g_HA2023	Anteil der Kinder_ deren Vater Elterngeld bezogen hat an allen anspruchsbegründeten Kindern im Jahr 2019 in _%	https://www.karto365.de/hosting/rest/services/elternv_g_HA2023/MapServer	elterng_v
teilz_m_HA2023	Männliche sozialversicherungspflichtig Beschäftigte in Teilzeit am Arbeitsort an den männlichen sozialversicherungspflichtig Beschäftigten im Jahr 2022 in _%	https://www.karto365.de/hosting/rest/services/teilz_m_HA2023/MapServer	teilz_m
p_sek_2_b	p_sek_2_b, feature	https://www.karto365.de/hosting/rest/services/p_sek_2_b/MapServer	
elade_ZA2023	Öffentlich zugängliche Ladepunkte für Elektrofahrzeuge im Jahr 2022 je 100_000 Einwohner__innen	https://www.karto365.de/hosting/rest/services/elade_ZA2023/MapServer	elade
elterng_v_HA2023	Anteil der Kinder_ deren Vater Elterngeld bezogen hat an allen anspruchsbegründeten Kindern im Jahr 2019 in _%	https://www.karto365.de/hosting/rest/services/elterng_v_HA2023/MapServer	elterng_v
straft_HA2022	Straftaten insgesamt pro 100_000 Einwohner__innen im Jahr 2021	https://www.karto365.de/hosting/rest/services/straft_HA2022/MapServer	straft
bquali_oabschl_HA2021	Anteil sozialversicherungspflichtig Beschäftigter am Arbeitsort ohne einen Berufs__ akademischen Abschluss an allen sozialversicherungspflichtig Beschäftigten im Jahr 2020 in %, bquali_oabschl_HA2021	https://www.karto365.de/hosting/rest/services/bquali_oabschl_HA2021/MapServer	bquali_oabschl
p_poli_b	K50, feature info, p_poli_b	https://www.karto365.de/hosting/rest/services/p_poli_b/MapServer	
p_ozmz_a	Durchschnittliche bevölkerungsgewichtete Pkw_Fahrzeit zum Stadtzentrum des nächsten Ober_ oder Mittelzentrum 2019 in Minuten, K29, p_ozmz, raster	https://www.karto365.de/hosting/rest/services/p_ozmz_a/MapServer	
kbetr_u3_HA2021	Anteil der betreuten Kinder unter 3 Jahren in Kindertageseinrichtungen__tagespflege an der Altersgruppe im Jahr 2019 in %, kbetr_u3_HA2021	https://www.karto365.de/hosting/rest/services/kbetr_u3_HA2021/MapServer	kbetr_u3
p_sek_2_a	Pkw_Fahrzeit zur nächsten Schule der Sekundarstufe II im Jahr 2015_2016_2017 in Minuten, K42, p_sek_2_a	https://www.karto365.de/hosting/rest/services/p_sek_2_a/MapServer	
v_lte_HA2021	Mobile Breitbandverfügbarkeit mit LTE ab 2Mbit_s in _ der Fläche im Jahr 2020, v_lte_HA2021	https://www.karto365.de/hosting/rest/services/v_lte_HA2021/MapServer	anteil_fla
grusi_HA2021	Anteil der Bevölkerung mit Grundsicherung im Alter an den 65_Jährigen und Älteren 2020 in _, grusi_HA2021	https://www.karto365.de/hosting/rest/services/grusi_HA2021/MapServer	grusi
v_breitb1000_HA2022	Anteil der Haushalte_ die mit einer Internetgeschwindigkeit von mindestens 1_000 Mbit_s versorgt werden können_ im Juni 2021 in _	https://www.karto365.de/hosting/rest/services/v_breitb1000_HA2022/MapServer	v_breitb1000
preis_baul_wms	Baulandpreise für Eigenheime im Jahr 2020 in € je m²	https://www.karto365.de/hosting/rest/services/preis_baul_wms/MapServer	
p_grunds_a	Pkw_Fahrzeit zur nächsten Grundschule im Jahr 2015_16_17 in Minuten, K40, p_grunds	https://www.karto365.de/hosting/rest/services/p_grunds_a/MapServer	
erw_wachs_ZA2022	Gemittelte Entwicklung der Erwerbstätigenzahl am Arbeitsort von 2009 bis 2019 pro Jahr in _	https://www.karto365.de/hosting/rest/services/erw_wachs_ZA2022/MapServer	erw_wachs
preis_baul_ZA2022	Baulandpreise für Eigenheime im Jahr 2020 in € je m²	https://www.karto365.de/hosting/rest/services/preis_baul_ZA2022/MapServer	
hh_veink_HA2021	Verfügbares Einkommen privater Haushalte je Einwohner__in im Jahr 2018 in 1_000 €, hh_veink_HA2021	https://www.karto365.de/hosting/rest/services/hh_veink_HA2021/MapServer	hh_veink
pendel_b_HA2022	Pendlerverflechtungen zwischen Gemeindeverbänden nach Anzahl der Pendler im Jahr 2020	https://www.karto365.de/hosting/rest/services/pendel_b_HA2022/MapServer	Pendler202
alq_HA2021	Arbeitslosenquote bezogen auf alle zivilen Erwerbspersonen im Jahr 2020 in %, alq_HA2021	https://www.karto365.de/hosting/rest/services/alq_HA2021/MapServer

# Feiertage API
https://feiertage-api.de/api/

# Hochwasser API
hochwasserzentralen.de API
 1.0.0 
OAS3
openapi.yaml
Das Länderübergreifendes Hochwasserportal (LHP) bietet auf https://www.hochwasserzentralen.de über die hier dokumentierte API Informationen zur Hochwassersituation in Deutschland an. Betreiber des LHP sind das Bayerische Landesamt für Umwelt (LfU) und die Landesanstalt für Umwelt Baden-Württemberg (LUBW). Die Urheberrechte an den veröffentlichten Daten liegen nach Auskunft der Betreiber bei der für das jeweilige Bundesland zuständigen Hochwasserzentrale bzw. beim jeweiligen Pegelbetreiber.

Länderübergreifendes Hochwasser Portal - Website
Servers

pegel


POST
​/webservices​/get_infospegel.php
Infos zu einem Pegel.

GET
​/webservices​/get_lagepegel.php
Lage der Pegel mit Pegelnummern
bundesland


POST
​/webservices​/get_infosbundesland.php
Infos zu einem Bundesland.

GET
​/webservices​/get_infosbundesland.php
Infos zu allen Bundesländern und angeschlossen Gebieten.

GET
​/vhosts​/geojson​/bundesland.{version}.geojson
Geojson der Bundesländer


# Luftqualität API
Umweltbundesamt Air Data API
 2.0.1 
OAS3
openapi.yaml
Air data API of Umweltbundesamt

Contact API Support
Servers

metadata


GET
​/components​/json
Get all components

GET
​/networks​/json
Get all networks

GET
​/scopes​/json
Get all scopes

GET
​/stationsettings​/json
Get all station settings

GET
​/stationtypes​/json
Get all station types

GET
​/thresholds​/json
Get all thresholds

GET
​/transgressiontypes​/json
Get all exceedances types

GET
​/meta​/json
Get combined metadata for use
airquality


GET
​/airquality​/json
Get airquality data

GET
​/airquality​/limits
Get airquality date limits
measurements


GET
​/measures​/json
Get all measurements

GET
​/measures​/limits
Get measurement date limits
exceedances


GET
​/transgressions​/json
Get exceedances data
annualtabulation


GET
​/annualbalances​/json
Get annualtabulation


# Strahlenschutz-API
Datenschnittstelle
Das Bundesamt für Strahlenschutz (BfS) stellt die Daten des ODL-Messnetzes kostenlos über eine standardisierte Datenschnittstelle zur Verfügung.
Bitte beachten Sie die Nutzungsbedingungen.
Das Bundesamt für Strahlenschutz (BfS) stellt die Daten des ODL-Messnetzes kostenlos über eine standardisierte Datenschnittstelle zur Verfügung. Es handelt sich dabei um den "Web Feature Service", einen Standard des Open Geospatial Consortiums (OGC).

Die beim BfS verfügbaren Geodatendienste werden auch im BfS-Geoportal bereitgestellt. Bitte beachten Sie die Nutzungsbedingungen für diese Dienste, die auch für die ODL-Datenschnittstelle gelten.

Hinweis: Zum 01.07.2025 haben wir die Methode zur Berechnung der ODL-Werte geändert. Dadurch kommt es zu einer geringen Erhöhung der Messwerte.

Datenformat

Die Daten werden von der Schnittstelle unter anderem im GeoJSON-Format ausgegeben. Hierbei handelt es sich um ein standardisiertes, offenes Format, welches Daten mit geografischem Bezug nach der Simple-Feature-Access-Spezifikation repräsentiert. Auch ODL-Info ruft die Daten in dieser Form ab.

Neben dem im Folgenden beschriebenen GeoJSON-Format ist ein Datenabruf auch in anderen Formaten (z.B. GML2, GML3, shape-zip, csv) möglich.

GeoJSON

Die Daten sind beim GeoJSON immer in einer FeatureCollection enthalten. Jedes Feature darin enthält neben den Koordinaten der jeweiligen Messstelle zudem auch die Messstellenkennung, den Namen der Messstelle und natürlich den entsprechenden Messwert inklusive Zeitstempel. Sofern die Anfrage fehlerfrei gestellt wurde, enthält die Antwort immer ein JSON-Objekt mit den folgenden Eigenschaften:

JSON-Objekt: Eigenschaften
Eigenschaft	Beschreibung
Jeder Eintrag im features-Array ist ein Objekt.
Unter der Eigenschaft properties enthält dieses wiederum ein Objekt mit den eigentlichen Daten. Die Daten sind dabei abhängig vom jeweiligen Layer.
Zudem sind unter der Eigenschaft geometry die Koordinaten der jeweiligen Messstelle verfügbar.
features	Ein Array mit den sogenannten "Features", also den eigentlichen Datensätzen.
totalFeatures	Anzahl der insgesamt von der Anfrage gefundenen Datensätzen.
numberReturned	Anzahl der für die Anfrage zurückgegebenen Datensätzen.
timeStamp	Zeitstempel der Antwort.
Verfügbare Informationen

Die verfügbaren Informationen werden in sogenannten Layern bereitgestellt. Jeder Layer enthält unterschiedliche Daten. Neben weiteren, teilweise optionalen, Parametern enthält die Abruf-URL immer den Layernamen.

Basis-Abruf-URL

https://www.imis.bfs.de/ogc/opendata/ows?service=WFS&version=1.1.0&request=GetFeature&typeName=opendata:<Layername>&outputFormat=application/json

Layer

Liste der Messstellen inklusive dem jeweils letzten 1-Stunden-MesswertEinklappen / Ausklappen
Layername

odlinfo_odl_1h_latest

Abruf-URL

https://www.imis.bfs.de/ogc/opendata/ows?service=WFS&version=1.1.0&request=GetFeature&typeName=opendata:odlinfo_odl_1h_latest&outputFormat=application/json

Properties der einzelnen Features
Property	Beschreibung
id	Die internationale ID der Messstelle.
kenn	Die Messstellenkennung, wie sie auch auf ODL-Info verwendet wird.
plz	Die Postleitzahl der Messstelle.
name	Der Name bzw. Ortsname der Messstelle.
site_status	Der Status der Messstelle als Zahl. (1 = in Betrieb, 2 = Defekt, 3 = Testbetrieb)
site_status_text	Der Status der Messstelle als Text.
kid	ID des Messnetzknotens, dem die Messstelle zugeordnet ist. (1 = Freiburg, 2 = Berlin, 3 = München, 4 = Bonn, 5 = Salzgitter, 6 = Rendsburg)
height_above_sea	Höhe der Messstelle über NN.
start_measure	Startzeitpunkt der Messperiode für den gegebenen Messwert.
end_measure
Endzeitpunkt der Messperiode für den gegebenen Messwert.
value	Der Messwert.
value_cosmic	Kosmischer Anteil des Messwertes.
value_terrestrial	Terrestrischer Anteil des Messwertes.
unit	Einheit zu dem Messwert.
validated	Prüfstatus des Messwertes. (1 = geprüft, 2 = ungeprüft)
nuclide	Bezeichnung der Messgröße.
duration	Dauer der Messperiode.
Beispiel

{


  "type": "FeatureCollection",


  "features": [


    {


      "type": "Feature",


      "id": "odlinfo_odl_1h_latest.fid-67f071dd_17b78091d3a_-1c2f",


      "geometry": {


        "type": "Point",


        "coordinates": [


          9.38,


          54.78


        ]


      },


      "geometry_name": "geom",


      "properties": {


        "id": "DEZ0001",


        "kenn": "010010001",


        "plz": "24941",


        "name": "Flensburg",


        "site_status": 1,


        "site_status_text": "in Betrieb",


        "kid": 6,


        "height_above_sea": 39,


        "start_measure": "2021-08-24T10:00:00Z",


        "end_measure": "2021-08-24T11:00:00Z",


        "value": 0.075,


        "value_cosmic": 0.043,


        "value_terrestrial": 0.033,


        "unit": "µSv/h",


        "validated": 1,


        "nuclide": "Gamma-ODL-Brutto",


        "duration": "1h"


      }


    },


    {


      "type": "Feature",


      "id": "odlinfo_odl_1h_latest.fid-67f071dd_17b78091d3a_-1c2e",


      "geometry": {


        "type": "Point",


        "coordinates": [


          9.05,


          54.02


        ]


      },


      "geometry_name": "geom",


      "properties": {


        "id": "DEZ0005",


        "kenn": "010510061",


        "plz": "25719",


        "name": "Barlt",


        "site_status": 1,


        "site_status_text": "in Betrieb",


        "kid": 6,


        "height_above_sea": 1,


        "start_measure": "2021-08-24T10:00:00Z",


        "end_measure": "2021-08-24T11:00:00Z",


        "value": 0.08,


        "value_cosmic": 0.042,


        "value_terrestrial": 0.038,


        "unit": "µSv/h",


        "validated": 1,


        "nuclide": "Gamma-ODL-Brutto",


        "duration": "1h"


      }


    },


    // [...]


  ],


  "totalFeatures": 1629,


  "numberMatched": 1629,


  "numberReturned": 1629,


  "timeStamp": "2021-08-24T12:12:03.304Z",


  "crs": {


    "type": "name",


    "properties": {


      "name": "urn:ogc:def:crs:EPSG::4326"


    }


  }


}
Zeitreihe mit 1-Stunden-MessdatenEinklappen / Ausklappen
Bei der Abfrage von Zeitreihendaten muss immer eine 9-stellige Messstellenkennung mit angegeben werden. Zusätzlich ist über einen Filter eine zeitliche Eingrenzung möglich.

Layername der Zeitreihe mit 1-Stunden-Messdaten

odlinfo_timeseries_odl_1h

Abruf-URL

https://www.imis.bfs.de/ogc/opendata/ows?service=WFS&version=1.1.0&request=GetFeature&typeName=opendata:odlinfo_timeseries_odl_1h&outputFormat=application/json&viewparams=kenn:<Messstellenkennung>

Properties der einzelnen Features
Property	Beschreibung
id	Die internationale ID (teilweise auch als locality_code bezeichnet) der Messstelle.
kenn	Die Messstellenkennung, wie sie auch auf ODL-Info verwendet wird.
plz	Die Postleitzahl der Messstelle.
name	Der Name bzw. Ortsname der Messstelle.
start_measure	Startzeitpunkt der Messperiode für den gegebenen Messwert.
end_measure
Endzeitpunkt der Messperiode für den gegebenen Messwert.
value	Der Messwert.
unit	Einheit zu dem Messwert.
validated	Prüfstatus des Messwertes. (1 = geprüft, 2 = ungeprüft)
nuclide	Bezeichnung der Messgröße.
duration	Dauer der Messperiode.
Beispiel

https://www.imis.bfs.de/ogc/opendata/ows?service=WFS&version=1.1.0&request=GetFeature&typeName=opendata:odlinfo_timeseries_odl_1h&outputFormat=application/json&viewparams=kenn:031020004

{


  "type": "FeatureCollection",


  "features": [


    {


      "type": "Feature",


      "id": "odlinfo_timeseries_odl_1h.fid-67f071dd_17b7820a5ac_40fc",


      "geometry": {


        "type": "Point",


        "coordinates": [


          10.33,


          52.15


        ]


      },


      "geometry_name": "geom",


      "properties": {


        "id": "DEZ2799",


        "kenn": "031020004",


        "name": "Salzgitter-Lebenstedt",


        "start_measure": "2021-08-17T12:00:00Z",


        "end_measure": "2021-08-17T13:00:00Z",


        "value": 0.088,


        "unit": "µSv/h",


        "validated": 1,


        "nuclide": "Gamma-ODL-Brutto",


        "duration": "1h"


      }


    },


    {


      "type": "Feature",


      "id": "odlinfo_timeseries_odl_1h.fid-67f071dd_17b7820a5ac_40fd",


      "geometry": {


        "type": "Point",


        "coordinates": [


          10.33,


          52.15


        ]


      },


      "geometry_name": "geom",


      "properties": {


        "id": "DEZ2799",


        "kenn": "031020004",


        "name": "Salzgitter-Lebenstedt",


        "start_measure": "2021-08-17T13:00:00Z",


        "end_measure": "2021-08-17T14:00:00Z",


        "value": 0.092,


        "unit": "µSv/h",


        "validated": 1,


        "nuclide": "Gamma-ODL-Brutto",


        "duration": "1h"


      }


    },


    // [...]


  ],


  "totalFeatures": 168,


  "numberMatched": 168,


  "numberReturned": 168,


  "timeStamp": "2021-08-24T12:30:21.262Z",


  "crs": {


    "type": "name",


    "properties": {


      "name": "urn:ogc:def:crs:EPSG::4326"


    }


  }


}
Zeitreihe mit 24-Stunden-MessdatenEinklappen / Ausklappen
Bei der Abfrage von Zeitreihendaten muss immer eine 9-stellige Messstellenkennung mit angegeben werden. Zusätzlich ist über einen Filter eine zeitliche Eingrenzung möglich.

Layername der Zeitreihe mit 24-Stunden-Messdaten

odlinfo_timeseries_odl_24h

Abruf-URL

https://www.imis.bfs.de/ogc/opendata/ows?service=WFS&version=1.1.0&request=GetFeature&typeName=opendata:odlinfo_timeseries_odl_24h&outputFormat=application/json&viewparams=kenn:<Messstellenkennung>

Properties der einzelnen Features
Property	Beschreibung
id	Die internationale ID (teilweise auch als locality_code bezeichnet) der Messstelle.
kenn	Die Messstellenkennung, wie sie auch auf ODL-Info verwendet wird.
plz	Die Postleitzahl der Messstelle.
name	Der Name bzw. Ortsname der Messstelle.
start_measure	Startzeitpunkt der Messperiode für den gegebenen Messwert.
end_measure
Endzeitpunkt der Messperiode für den gegebenen Messwert.
value	Der Messwert.
unit	Einheit zu dem Messwert.
validated	Prüfstatus des Messwertes. (1 = geprüft, 2 = ungeprüft)
nuclide	Bezeichnung der Messgröße.
duration	Dauer der Messperiode.
Beispiel

https://www.imis.bfs.de/ogc/opendata/ows?service=WFS&version=1.1.0&request=GetFeature&typeName=opendata%3Aodlinfo_timeseries_odl_24h&viewparams=kenn%3A031020004&outputFormat=application%2Fjson

{


  "type": "FeatureCollection",


  "features": [


    {


      "type": "Feature",


      "id": "odlinfo_timeseries_odl_24h.fid-67f071dd_17b784e2b46_-2dcf",


      "geometry": {


        "type": "Point",


        "coordinates": [


          10.33,


          52.15


        ]


      },


      "geometry_name": "geom",


      "properties": {


        "id": "DEZ2799",


        "kenn": "031020004",


        "name": "Salzgitter-Lebenstedt",


        "start_measure": "2020-08-24T00:00:00Z",


        "end_measure": "2020-08-25T00:00:00Z",


        "value": 0.097,


        "unit": "µSv/h",


        "validated": 1,


        "nuclide": "Gamma-ODL-Brutto",


        "duration": "1d"


      }


    },


    {


      "type": "Feature",


      "id": "odlinfo_timeseries_odl_24h.fid-67f071dd_17b784e2b46_-2dce",


      "geometry": {


        "type": "Point",


        "coordinates": [


          10.33,


          52.15


        ]


      },


      "geometry_name": "geom",


      "properties": {


        "id": "DEZ2799",


        "kenn": "031020004",


        "name": "Salzgitter-Lebenstedt",


        "start_measure": "2020-08-25T00:00:00Z",


        "end_measure": "2020-08-26T00:00:00Z",


        "value": 0.099,


        "unit": "µSv/h",


        "validated": 1,


        "nuclide": "Gamma-ODL-Brutto",


        "duration": "1d"


      }


    },


    // [...]


  ],


  "totalFeatures": 345,


  "numberMatched": 345,


  "numberReturned": 345,


  "timeStamp": "2021-08-24T13:29:20.877Z",


  "crs": {


    "type": "name",


    "properties": {


      "name": "urn:ogc:def:crs:EPSG::4326"


    }


  }


}
Sortierung, Filtermöglichkeiten und alternative Datenformate

Die zurückgegebenen Daten einer Anfrage können direkt über die Anfrage sortiert, begrenzt und gefiltert werden. Zudem ist die Ausgabe auch in anderen Datenformaten möglich.

Sortierung
Filterung
Datenformate
Sortierung der ausgegebenen Daten nach Eigenschaften

Die Daten können nach jeder in den "properties" enthaltenen Eigenschaft der Features sortiert werden. Sinnvoll kann beispielsweise eine Sortierung nach "end_measure" sein, wodurch die Daten nach dem Ende der Messperiode sortiert ausgegeben werden.

Zusätzlich kann +A für eine aufsteigende (Standard) oder +D für eine absteigende Sortierung angehängt werden.

Beispiele dafür sind

https://www.imis.bfs.de/ogc/opendata/ows?service=WFS&version=1.1.0&request=GetFeature&typeName=opendata:odlinfo_timeseries_odl_1h&outputFormat=application/json&viewparams=kenn:031020004&sortBy=end_measure
https://www.imis.bfs.de/ogc/opendata/ows?service=WFS&version=1.1.0&request=GetFeature&typeName=opendata:odlinfo_timeseries_odl_1h&outputFormat=application/json&viewparams=kenn:031020004&sortBy=end_measure+D

-ODL-Info API
 1.0.0 
OAS3
openapi.yaml
Daten zur radioaktiven Belastung in Deutschland. Weitere Informationen unter https://odlinfo.bfs.de/ODL/DE/service/datenschnittstelle/datenschnittstelle_node.html.

Servers

default


GET
​/
Hauptendpunkt

# Studienangebote
Arbeitsagentur Studiensuche API
 1.0.1 
OAS3
openapi.yaml
Eine der größten Datenbanken für Studienangebote in Deutschland durchsuchen.

Die Authentifizierung funktioniert über eine clientId:

clientId: infosysbub-studisu

Die clientId muss bei folgenden GET-requests an https://rest.arbeitsagentur.de/infosysbub/studisu/pc/v1/studienangebote als Header-Parameter 'X-API-Key' zu übergeben.

AndreasFischer1985 - Website
Send email to AndreasFischer1985
Weiterführende Dokumentation
Servers

Authorize
default


GET
​/pc​/v1​/studienangebote
Studiensuche

# Tagesschau API

[DE]/[EN]

Tagesschau API

Die Tagesschau ist eine Nachrichtensendung der ARD (Abkürzung für Arbeitsgemeinschaft der öffentlich-rechtlichen Rundfunkanstalten der Bundesrepublik Deutschland), die von ARD-aktuell in Hamburg produziert und mehrmals täglich ausgestrahlt wird. ARD-aktuell ist seit 1977 die zentrale Fernsehnachrichtenredaktion der ARD, bei welcher es sich wiederum um einen Rundfunkverbund handelt, der aus den Landesrundfunkanstalten und der Deutschen Welle besteht.

Über die hier dokumentierte API stehen auf www.tagesschau.de aktuelle Nachrichten und Medienbeiträge im JSON-Format zur Verfügung.

ACHTUNG: Die Nutzung der Inhalte für den privaten, nicht-kommerziellen Gebrauch ist gestattet, die Veröffentlichung hingegen nicht - mit Ausnahme von Angeboten, die explizit unter der CC-Lizenz stehen (https://tagesschau.de/creativecommons). Es ist unzulässig, mehr als 60 Abrufe pro Stunde zu tätigen.

Homepage

URL: https://www.tagesschau.de/api2u/homepage/

Ausgewählte Nachrichten und Eilmeldungen, die auf der Startseite der Tagesschau-App zu sehen sind.

News

URL: https://www.tagesschau.de/api2u/news/

Aktuelle Nachrichten, die über GET-Parameter gefiltert werden können:

Parameter: regions

1
2
3
4
5
6
7
8
9
10
11
12
13
14
15
16
Bundesland: 1=Baden-Württemberg, 2=Bayern, 3=Berlin, 4=Brandenburg, 5=Bremen, 6=Hamburg, 7=Hessen, 8=Mecklenburg-Vorpommern, 9=Niedersachsen, 10=Nordrhein-Westfalen, 11=Rheinland-Pfalz, 12=Saarland, 13=Sachsen, 14=Sachsen-Anhalt, 15=Schleswig-Holstein, 16=Thüringen. Mehrere Komma-getrennte Angaben möglich (z.B. regions=1,2).

Parameters: ressort

inland
ausland
wirtschaft
sport
video
investigativ
wissen
Ressort/Themengebiet

Channels

URL: https://www.tagesschau.de/api2u/channels/

Aktuelle Kanäle (im Livestream: tagesschau24, tagesschau in 100 Sekunden, tagesschau, tagesschau 20 Uhr, tagesthemen, nachtmagazin, Bericht aus Berlin, tagesschau vor 20 Jahren, tagesschau mit Gebärdensprache)

Search

URL: https://www.tagesschau.de/api2u/search/

Parameter: searchText

Suchtext

Parameter: resultPage

Seite

Parameter: pageSize

Suchergebnisse pro Seite (1-30)

Beispiel

tagesschau=$(curl -m 60 https://www.tagesschau.de/api2/homepage/)

--

Tagesschau API
 2.0.1 
OAS3
openapi.yaml
Die Tagesschau ist eine Nachrichtensendung der ARD (Abkürzung für Arbeitsgemeinschaft der öffentlich-rechtlichen Rundfunkanstalten der Bundesrepublik Deutschland), die von ARD-aktuell in Hamburg produziert und mehrmals täglich ausgestrahlt wird. ARD-aktuell ist seit 1977 die zentrale Fernsehnachrichtenredaktion der ARD, bei welcher es sich wiederum um einen Rundfunkverbund handelt, der aus den Landesrundfunkanstalten und der Deutschen Welle besteht.

Über die hier dokumentierte API stehen auf www.tagesschau.de aktuelle Nachrichten und Medienbeiträge im JSON-Format zur Verfügung.

Achtung: Die Nutzung der Inhalte für den privaten, nicht-kommerziellen Gebrauch ist gestattet, die Veröffentlichung hingegen nicht - mit Ausnahme von Angeboten, die explizit unter der CC-Lizenz stehen (https://tagesschau.de/creativecommons). Es ist unzulässig, mehr als 60 Abrufe pro Stunde zu tätigen.

AndreasFischer1985 - Website
Send email to AndreasFischer1985
Servers

homepage


GET
​/api2u​/homepage​/
Ausgewählte aktuelle Nachrichten und Eilmeldungen
news


GET
​/api2u​/news​/
Aktuelle Nachrichten und Eilmeldungen
channels


GET
​/api2u​/channels​/
Aktuelle Kanäle
search


GET
​/api2u​/search​/
Suche


# Reisewarnung API
uswärtiges Amt: Reisewarnungen OpenData Schnittstelle
 1.2.6 
OAS3
openapi.yaml
Reisewarnungen OpenData Schnittstelle. Dies ist die Beschreibung für die Schnittstelle zum Zugriff auf die Daten des Auswärtigen Amtes im Rahmen der OpenData Initiative.

Deaktivierung

Die Schnittstelle kann deaktiviert werden, in dem Fall wird ein leeres JSON-Objekt zurückgegeben.

Fehlerfall

Im Fehlerfall wird ein leeres JSON-Objekt zurückgegeben.

Nutzungsbedingungen

Die Nutzungsbedingungen sind auf der OpenData-Schnittstelle des Auswärtigen Amtes zu finden.

Änderungen (offizielles Changelog)

version 1.2.7 - (02.08.2022)

Dreistellige ISO-Ländercodes (ISO 3166-1 alpha-3) wurden als iso3CountryCode hinzugefügt.

version 1.2.6 - (08.12.2021)

Es werden zusätzlich zu jedem Land Ländercodes mit jeweils zwei Buchstaben mit ausgegeben. Die Länderkürzel werden bei /travelwarning und /travelwarning/{contentId} in einem neuen Attribut ausgegeben z.B. in: /travelwarning/199124.

version 1.2.5 (ursprünglich geplant für Ende September 2021)

content (-> Details des Reise- und Sicherheitshinweis) wurde von /travelwarning entfernt -> bitte ab jetzt /travelwarning/{contentId} nutzen um content abzufragen flagURL (-> Details des Reise- und Sicherheitshinweis) wurde entfernt -> es werden keine Flaggen mehr angeboten

Terms of service
Servers

default


GET
​/travelwarning
Gibt alle Reise- und Sicherheitshinweise zurück

GET
​/travelwarning​/{contentId}
Gibt einen Reise- und Sicherheitshinweis zurück

GET
​/representativesInGermany
Gibt eine Liste der ausländischen Vertretungen in Deutschland zurück

GET
​/representativesInCountry
Gibt eine Liste der deutschen Vertretungen im Ausland zurück

GET
​/stateNames
Gibt das Verzeichnis der Staatennamen zurück

GET
​/healthcare
Gibt die Merkblätter des Gesundheitsdienstes zurück

# HomeAssistant API

REST API

Home Assistant provides a RESTful API on the same port as the web frontend (default port is port 8123).

If you are not using the frontend in your setup then you need to add the api integration to your configuration.yaml file.

http://IP_ADDRESS:8123/ is an interface to control Home Assistant.
http://IP_ADDRESS:8123/api/ is a RESTful API.
The API accepts and returns only JSON encoded objects.

All API calls have to be accompanied by the header Authorization: Bearer TOKEN, where TOKEN is replaced by your unique access token. You obtain a token ("Long-Lived Access Token") by logging into the frontend using a web browser, and going to your profile http://IP_ADDRESS:8123/profile. Be careful to copy the whole key.

There are multiple ways to consume the Home Assistant Rest API. One is with curl:

curl \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  http://IP_ADDRESS:8123/ENDPOINT

Another option is to use Python and the Requests module.

from requests import get

url = "http://localhost:8123/ENDPOINT"
headers = {
    "Authorization": "Bearer TOKEN",
    "content-type": "application/json",
}

response = get(url, headers=headers)
print(response.text)

Another option is to use the RESTful Command integration in a Home Assistant automation or script.

turn_light_on:
  url: http://localhost:8123/api/states/light.study_light
  method: POST
  headers:
    authorization: 'Bearer TOKEN'
    content-type: 'application/json'
  payload: '{"state":"on"}'

Successful calls will return status code 200 or 201. Other status codes that can return are:

400 (Bad Request)
401 (Unauthorized)
404 (Not Found)
405 (Method Not Allowed)
Actions

The API supports the following actions:

GET
/api/
🔒
GET
/api/config
🔒
GET
/api/components
🔒
GET
/api/events
🔒
GET
/api/services
🔒
GET
/api/history/period/<timestamp>
🔒
GET
/api/logbook/<timestamp>
🔒
GET
/api/states
🔒
GET
/api/states/<entity_id>
🔒
GET
/api/error_log
🔒
GET
/api/camera_proxy/<camera entity_id>
🔒
GET
/api/calendars
🔒
GET
/api/calendars/<calendar entity_id>?start=<timestamp>&end=<timestamp>
🔒
POST
/api/states/<entity_id>
🔒
POST
/api/events/<event_type>
🔒
POST
/api/services/<domain>/<service>
🔒
POST
/api/template
🔒
POST
/api/config/core/check_config
🔒
POST
/api/intent/handle
🔒
DELETE
/api/states/<entity_id>

# Uptime Kuma API

Uptime Kuma API Documentation (Detailed)

⚠️ IMPORTANT NOTE: This documentation describes Uptime Kuma's internal API. This API is primarily designed for the application's own use and is not officially supported for third-party integrations. Breaking changes may occur between versions without prior notice. Use at your own risk.
Uptime Kuma primarily uses Socket.io for real-time communication after authentication. It also provides RESTful API endpoints for push monitors, status badges, Prometheus metrics, and public status page data.

Authentication

REST API

Push Monitors (/api/push/:pushToken): Authenticated via the unique :pushToken in the URL path. No other authentication needed for this endpoint.
Metrics (/metrics): Authentication depends on server settings (Settings -> Security -> API Keys):
API Key Authentication (If Enabled):
Method: HTTP Basic Auth.
Username: (empty string or any value, it's ignored).
Password: Your generated API Key (e.g., uk2_somereallylongkey).
Basic User Authentication (If API Keys Disabled or Not Provided):
Method: HTTP Basic Auth.
Username: Your Uptime Kuma username.
Password: Your Uptime Kuma password.
No Authentication (If Auth Disabled in Settings):
No credentials required. Access is open.
Badges & Public Status Pages: These endpoints are generally public. Access to monitor-specific badges depends on the monitor being included in a public group on any status page. Status page data endpoints (/api/status-page/...) require the status page itself to be published.
Socket.io API

Establish a Socket.io connection.
Authentication: The client must authenticate after connection using one of these events:
login Event: Provide username, password, and optionally a 2FA token.
loginByToken Event: Provide a JWT token obtained from a previous successful login where "Remember Me" was selected.
Authorization: Once authenticated via login or loginByToken, all subsequent events sent on that specific socket connection are authorized for the logged-in user.
Common Data Structures

(Used in Socket.io events and some API responses)

Monitor Object (Partial Example):
{
  "id": 1,
  "name": "My Website",
  "type": "http",
  "url": "https://example.com",
  "method": "GET",
  "interval": 60,
  "retryInterval": 60,
  "resendInterval": 0,
  "maxretries": 0,
  "hostname": null,
  "port": null,
  "active": true,
  "tags": [
    {
      "tag_id": 1,
      "monitor_id": 1,
      "value": null,
      "name": "production",
      "color": "#059669"
    }
  ],
  "notificationIDList": { "1": true },
  // ... other monitor-type specific fields
  "accepted_statuscodes_json": "[\"200-299\"]",
  "conditions": "[]" // JSON string of condition groups
}
Heartbeat Object:
{
  "monitorID": 1,
  "status": 1, // 0=DOWN, 1=UP, 2=PENDING, 3=MAINTENANCE
  "time": "2023-10-27T10:30:00.123Z", // ISO 8601 UTC Timestamp
  "msg": "OK",
  "ping": 123, // Response time in ms, null if not applicable
  "important": true, // Was this heartbeat a status change?
  "duration": 60, // Seconds since the last heartbeat for this monitor
  "localDateTime": "2023-10-27 12:30:00", // Formatted time in server's timezone
  "timezone": "Europe/Berlin", // Server's timezone name
  "retries": 0, // Number of retries attempted for this state
  "downCount": 0 // Consecutive down count for resend logic
}
Notification Object (Partial Example):
{
  "id": 1,
  "name": "My Telegram Bot",
  "active": true,
  "isDefault": false,
  "userID": 1,
  "config": "{\"type\":\"telegram\",\"telegramBotToken\":\"...\",\"telegramChatID\":\"...\",\"name\":\"My Telegram Bot\",\"isDefault\":false,\"applyExisting\":false}" // JSON string
}
REST API Endpoints

Push Endpoint

Receive updates for "Push" type monitors.

Endpoint: /api/push/<pushToken>
Method: GET | POST | PUT | PATCH (Method is generally ignored)
Authentication: Push Token (<pushToken> in the path)
Path Parameters:
pushToken (string, required): The unique token associated with the push monitor.
Query Parameters:
status (string, optional): Status of the service. "up" or "down". Defaults to "up".
msg (string, optional): A message describing the status. Defaults to "OK". Max length approx. 250 chars.
ping (number, optional): Response time in milliseconds. Parsed as float. Defaults to null.
Success Response (200 OK):
{
  "ok": true
}
Error Response (404 Not Found):
{
  "ok": false,
  "msg": "Monitor not found or not active."
}
Badge Endpoints

Provide status badges for monitors associated with a public status page group.

Status Badge:

Endpoint: /api/badge/<id>/status
Response: SVG image.
(See previous documentation for query parameters)
Uptime Badge:

Endpoint: /api/badge/<id>/uptime[/<duration>] (e.g., /uptime/24h, /uptime/7d)
Response: SVG image.
(See previous documentation for query parameters)
Ping/Response Time Badge:

Endpoint: /api/badge/<id>/ping[/<duration>] (e.g., /ping/24h, /ping/7d)
Response: SVG image.
(See previous documentation for query parameters)
Note: /avg-response and /response variants also exist.
Certificate Expiry Badge:

Endpoint: /api/badge/<id>/cert-exp
Response: SVG image.
(See previous documentation for query parameters)
Status Page Endpoints

Provide data for published public status pages.

Get Status Page Data:

Endpoint: /api/status-page/<slug>
Method: GET
Authentication: None (Requires Status Page to be published)
Path Parameters:
slug (string, required): The unique slug of the status page.
Success Response (200 OK):
{
  "config": {  // StatusPage config object
    "slug": "my-status",
    "title": "My Service Status",
    "description": "Current status of our services.",
    "icon": "/icon.svg",
    "theme": "light",
    "published": true,
    "showTags": false
    // ... other config fields
  },
  "incident": null | { // Pinned incident object or null
    "id": 1,
    "title": "Investigating Network Issues",
    "content": "We are currently investigating network latency.",
    "style": "warning",
    "createdDate": "2023-10-27T10:00:00.000Z",
    "lastUpdatedDate": "2023-10-27T10:15:00.000Z",
    "pin": true
  },
  "publicGroupList": [ // Array of public monitor groups
    {
      "id": 1,
      "name": "Core Services",
      "weight": 0,
      "monitorList": [ // Array of Monitor objects within the group
        {
          "id": 1,
          "name": "Website",
          "type": "http"
          // ... other *public* monitor fields
        }
        // ... more monitors
      ]
    }
    // ... more groups
  ],
  "maintenanceList": [ // Array of active/scheduled Maintenance objects relevant to this page
    {
        "id": 1,
        "title": "Scheduled Server Upgrade",
        "description": "Upgrading server hardware.",
        "strategy": "single", // or "recurring-...", "manual", "cron"
        "active": true,
        "status": "scheduled", // "scheduled", "under-maintenance", "ended", "inactive"
        "timeslotList": [
            {
                "startDate": "2023-11-01T02:00:00.000Z",
                "endDate": "2023-11-01T04:00:00.000Z"
            }
            // ... more timeslots possible for recurring
        ]
        // ... other fields like timezone, weekdays etc.
    }
  ]
}
Error Response (404 Not Found): If slug doesn't exist or status page is not published.
Get Status Page Heartbeats & Uptime:

Endpoint: /api/status-page/heartbeat/<slug>
Method: GET
Authentication: None (Requires Status Page to be published)
Path Parameters:
slug (string, required): The status page slug.
Success Response (200 OK):
{
  "heartbeatList": {
    "1": [
      // Monitor ID 1
      { "status": 1, "time": "...", "msg": "OK", "ping": 55 }
      // ... more heartbeats (up to 100 recent)
    ],
    "2": [
      // Monitor ID 2
      {
        "status": 0,
        "time": "...",
        "msg": "Timeout",
        "ping": null
      }
      // ...
    ]
  },
  "uptimeList": {
    "1_24": 0.9998, // Monitor ID 1, 24h uptime percentage
    "2_24": 0.95 // Monitor ID 2, 24h uptime percentage
    // ... potentially other periods if requested differently in future
  }
}
Error Response (404 Not Found): If slug doesn't exist or status page is not published.
Get Status Page Manifest:

Endpoint: /api/status-page/<slug>/manifest.json
Method: GET
Response: Standard Web App Manifest JSON.
(See previous documentation for structure)
Get Overall Status Page Badge:

Endpoint: /api/status-page/<slug>/badge
Method: GET
Response: SVG image.
(See previous documentation for query parameters and logic)
Metrics Endpoint

Exposes internal metrics for Prometheus scraping.

Endpoint: /metrics
Method: GET
Authentication: API Key or Basic Auth (See Authentication section)
Response: Plain text in Prometheus exposition format. Includes gauges like:
monitor_status{monitor_name="...", monitor_type="...", ...} (Value: 0, 1, 2, 3)
monitor_response_time{...} (Value: milliseconds)
monitor_cert_days_remaining{...} (Value: days)
monitor_cert_is_valid{...} (Value: 0 or 1)
Entry Page Endpoint

Used by the frontend to determine the initial landing page.

Endpoint: /api/entry-page
Method: GET
Authentication: None
Success Response (200 OK):
If domain matches a status page:
{ "type": "statusPageMatchedDomain", "statusPageSlug": "<your-slug>" }
If standard entry:
{ "type": "entryPage", "entryPage": "dashboard" | "statusPage-<your-slug>" }
Socket.io API

Real-time interaction occurs over Socket.io after successful authentication.

General Flow

Client connects.
Server may send loginRequired.
Client sends login or loginByToken.
Server responds via callback.
If login OK, server sends initial data (monitorList, heartbeatList, etc.).
Client sends commands (e.g., addMonitor, pauseMonitor), server responds via callback.
Server pushes real-time updates (heartbeat, avgPing, uptime, list updates).
Client-Sent Events (Selected Detail)

(Format: eventName(data, callback(res)) )

Authentication:

login
Data: { username: "<string>", password: "<string>", token?: "<string>" } (2FA token if needed)
Callback: res: { ok: <boolean>, msg?: "<string>", msgi18n?: <boolean>, token?: "<jwt_string>", tokenRequired?: <boolean> }
Description: Attempts to log in. Returns tokenRequired: true if 2FA is enabled and token wasn't provided. Returns JWT token on success.
loginByToken
Data: jwtToken: "<string>"
Callback: res: { ok: <boolean>, msg?: "<string>", msgi18n?: <boolean> }
Description: Logs in using a previously obtained JWT.
logout
Callback: (Optional) res: {}
Description: Logs the current user out.
Monitor Management:

add
Data: monitor: <MonitorObject> (without id)
Callback: res: { ok: <boolean>, msg?: "<string>", msgi18n?: <boolean>, monitorID?: <number> }
Description: Adds a new monitor configuration.
editMonitor
Data: monitor: <MonitorObject> (with id)
Callback: res: { ok: <boolean>, msg?: "<string>", msgi18n?: <boolean>, monitorID?: <number> }
Description: Updates an existing monitor configuration.
deleteMonitor
Data: monitorID: <number>
Callback: res: { ok: <boolean>, msg?: "<string>", msgi18n?: <boolean> }
pauseMonitor / resumeMonitor
Data: monitorID: <number>
Callback: res: { ok: <boolean>, msg?: "<string>", msgi18n?: <boolean> }
getMonitor
Data: monitorID: <number>
Callback: res: { ok: <boolean>, monitor?: <MonitorObject>, msg?: "<string>" }
getMonitorBeats
Data: monitorID: <number>, period: <number> (in hours)
Callback: res: { ok: <boolean>, data?: [<HeartbeatObject>], msg?: "<string>" }
getMonitorChartData
Data: monitorID: <number>, period: <number> (in hours)
Callback: res: { ok: <boolean>, data?: [<UptimeCalculatorDataPoint>], msg?: "<string>" }
Note: <UptimeCalculatorDataPoint> has fields like timestamp, up, down, ping, pingMin, pingMax.
Notification Management:

addNotification
Data: notification: <NotificationObject> (Config is stringified JSON), notificationID: <number> | null (null for add, ID for edit)
Callback: res: { ok: <boolean>, msg?: "<string>", msgi18n?: <boolean>, id?: <number> }
deleteNotification
Data: notificationID: <number>
Callback: res: { ok: <boolean>, msg?: "<string>", msgi18n?: <boolean> }
testNotification
Data: notification: <NotificationObject> (Config is stringified JSON)
Callback: res: { ok: <boolean>, msg?: "<string>" }
Settings:

getSettings
Callback: res: { ok: <boolean>, data?: <object>, msg?: "<string>" } (Data contains general settings)
setSettings
Data: settings: <object>, currentPassword: "<string>" (Required only if enabling auth or changing sensitive settings while auth is on)
Callback: res: { ok: <boolean>, msg?: "<string>", msgi18n?: <boolean> }
changePassword
Data: passwords: { currentPassword: "<string>", newPassword: "<string>" }
Callback: res: { ok: <boolean>, msg?: "<string>", msgi18n?: <boolean>, token?: "<jwt_string>" }
Status Page Management:

addStatusPage
Data: title: "<string>", slug: "<string>"
Callback: res: { ok: <boolean>, msg?: "<string>", msgi18n?: <boolean>, slug?: "<string>" }
saveStatusPage
Data: slug: "<string>", config: <StatusPageConfigObject>, imgDataUrl: "<string>", publicGroupList: [<PublicGroupObject>]
Callback: res: { ok: <boolean>, msg?: "<string>", publicGroupList?: [<PublicGroupObject>] }
deleteStatusPage
Data: slug: "<string>"
Callback: res: { ok: <boolean>, msg?: "<string>" }
postIncident
Data: slug: "<string>", incident: <IncidentObject>
Callback: res: { ok: <boolean>, incident?: <IncidentObject>, msg?: "<string>" }
unpinIncident
Data: slug: "<string>"
Callback: res: { ok: <boolean>, msg?: "<string>" }
(Other events for Maintenance, API Keys, Tags, Proxies, Docker, Remote Browsers, 2FA, Database actions follow a similar pattern: send data object, receive { ok: ..., msg: ... } via callback)

Server-Sent Events (Selected Detail)

monitorList
Payload: { <monitorID>: <MonitorObject>, ... }
Description: Full list of monitors the user has access to. Sent on connect/login or major list change.
updateMonitorIntoList
Payload: { <monitorID>: <MonitorObject>, ... }
Description: Updated data for one or more specific monitors.
deleteMonitorFromList
Payload: monitorID: <number>
Description: Sent when a monitor is deleted.
heartbeat
Payload: <HeartbeatObject>
Description: Real-time heartbeat update for a monitor.
avgPing
Payload: monitorID: <number>, avgPing: <number> | null
Description: Updated 24-hour average ping.
uptime
Payload: monitorID: <number>, periodKey: "<string>", percentage: <number> (e.g., periodKey "24" for 24h uptime)
Description: Updated uptime percentage for a specific period.
certInfo
Payload: monitorID: <number>, tlsInfoJSON: "<string>" (JSON string of TLS details)
Description: Updated TLS certificate information.
(Other list events notificationList, maintenanceList, etc. send arrays or objects representing the respective items.)
refresh
Description: Tells the client UI to reload the page (e.g., after password change).
info
Payload: { version: "<string>", latestVersion: "<string>", primaryBaseURL: "<string>", serverTimezone: "<string>" }
Description: Basic server information.
Error Handling

Most callback responses (res) from client-sent events will include ok: false and a msg property containing an error description if the operation failed on the server-side. The msgi18n flag indicates if the msg is an i18n key.
Connection errors (connect_error, disconnect) are handled by the client to show appropriate messages.
Disclaimer: This documentation is generated based on analysis of the provided source code. While aiming for accuracy, it might not cover every implementation detail or edge case. Always refer to the source code for definitive behavior.