# PENDING-ARMS ledger triage — 2026-09-24

> Scope: the 682 rows `scripts/pending_arms_report.py` buckets TECH-DEBT-OVERDUE on main @ `29aff505`. OPERATOR-GATED (243), FIREBREAK (29) and NATURAL-WAIT (9) rows were not audited. An ID `L<n>` is the row's line number at that commit — read it with `git show 29aff505:.claude/skills/modus/PENDING-ARMS.md | sed -n '<n>p'`.

Full per-row table (title, missing step, files to touch, fix-size estimate, the auditor's command and output, both refuters' verdicts): <https://claude.ai/artifact/7rNjCs3ZmtFbYDHwEsyiu8> (private to the owner's account; a Claude session on that account reads it with the Artifact tool).

## Method

- **Classify:** 35 read-only shards of up to 20 rows, one auditor each, in a cloud container (shallow clone, no reach to the Macs, Fly or production). Every verdict is backed by a command run in that turn.
- **Verify (generator ≠ grader):** each CURED/OBSOLETE claim (166) was re-derived by two independent adversarial refuters on a different model: _reproduce_ re-ran the proof and looked for what it missed; _W81-scope_ looked for any part of the arming that repo evidence cannot prove (deploy, machine state, prod data, operator act). A row is closed only when both confirm.
- **Close:** confirmed rows are flipped in place from `- opened` to `- closed 2026-09-24 (…)`, with the reproduce refuter's proof and the scope refuter's reason appended to the row itself.

## Counts

| Verdict                |    Rows | Meaning                                                                 |
| ---------------------- | ------: | ----------------------------------------------------------------------- |
| CURED                  |      78 | closed in this PR — arming fully proven from main                       |
| OBSOLETE               |      15 | closed in this PR — surface gone, or an exact duplicate of a closed row |
| CURED-NEEDS-LIVE-PROBE |      55 | repo side done; one probe on a Mac, Fly or prod closes it               |
| OPEN-REPO-FIXABLE      |     402 | still open; a cloud session can fix it in the repo                      |
| NEEDS-MAC-PROD         |      98 | still open; fixing it needs Pro/Mini/M5, Fly or prod                    |
| OPERATOR-BUSINESS      |      22 | needs a human decision or act — mis-filed as TECH-DEBT                  |
| UNCLEAR                |      12 | not decidable from here, including 4 held-back duplicates (below)       |
| **total**              | **682** |                                                                         |

Closure claims: 166 made, 69 refuted by at least one refuter (41% — the auditor-alone false-closure rate this sweep measured), 93 closed. `pending_arms_report.py` tech_debt_overdue: 683 → 590.

## Held back — an identical copy was judged open (4)

These rows exist twice, word for word (a `merge=union` duplicate). One copy survived both refuters; the other copy went to a different auditor who judged it open. Neither copy is closed. Re-verify once, then close or keep both copies together.

- L1427 (claimed CURED) — copy L1395 judged open
- L1433 (claimed CURED) — copy L1401 judged open
- L1439 (claimed CURED) — copy L1407 judged open
- L1447 (claimed CURED) — copy L1415 judged open

## Work queue — OPEN-REPO-FIXABLE (402)

Grouped by value, smallest estimated fix first. Re-verify a row on current main before building its fix.

- **high (160):** L42, L1470, L1472, L349, L564, L773, L1266, L1405, L1437, L1775, L1820, L2060, L345, L440, L592, L847, L1107, L1161, L1299, L1728, L1285, L1330, L1395, L1999, L2104, L841, L1355, L1383, L1627, L1897, L17, L68, L492, L493, L733, L1032, L1129, L1301, L1308, L1351, L1397, L1429, L1755, L1791, L1856, L1859, L1860, L913, L1326, L1726, L1802, L60, L1331, L1364, L1381, L1606, L1613, L1842, L1997, L2043, L2100, L1287, L58, L200, L347, L845, L1081, L1453, L1469, L1519, L1600, L1631, L1760, L1772, L1824, L1853, L2145, L2305, L951, L1334, L1736, L82, L292, L840, L854, L1315, L1618, L1800, L1852, L1888, L2188, L663, L1541, L816, L898, L1857, L2010, L2284, L28, L168, L343, L804, L1466, L1509, L1851, L1382, L1787, L166, L655, L829, L912, L1300, L1314, L1333, L1336, L1474, L1617, L1632, L1953, L1739, L1306, L1778, L1947, L107, L461, L1475, L2233, L148, L303, L482, L650, L740, L1258, L1604, L1637, L1792, L431, L634, L2271, L1633, L31, L1588, L1777, L2225, L23, L37, L1256, L1295, L1323, L1340, L1391, L1393, L1423, L1425, L1467, L1491, L1537, L1797, L1898, L1745
- **medium (175):** L1172, L868, L1183, L191, L193, L1403, L1407, L1641, L1891, L961, L2109, L301, L2072, L1171, L1188, L1321, L1435, L1626, L2093, L1723, L352, L803, L982, L1139, L1146, L1378, L1399, L1471, L1621, L1794, L2094, L801, L820, L1337, L1625, L1738, L1750, L1803, L1890, L1991, L2012, L2103, L610, L959, L1134, L1297, L1302, L1431, L1460, L1727, L1773, L1870, L780, L920, L971, L1087, L1298, L1596, L1788, L1835, L1967, L2027, L2106, L2113, L2282, L1309, L1523, L2313, L65, L436, L588, L623, L673, L823, L881, L930, L973, L1084, L1201, L1294, L1468, L1550, L1592, L1628, L1643, L1774, L2042, L2110, L1288, L1504, L1998, L622, L1097, L1752, L1798, L1838, L35, L50, L185, L653, L672, L782, L810, L1130, L1176, L1374, L1608, L1780, L1786, L333, L562, L627, L657, L796, L1339, L26, L52, L318, L561, L970, L1013, L1105, L1563, L1634, L1642, L1899, L146, L626, L940, L1109, L1307, L1779, L1039, L1635, L1882, L97, L559, L905, L964, L1564, L1935, L1272, L566, L802, L928, L1455, L1895, L1296, L669, L1650, L1720, L150, L1274, L1638, L1880, L209, L1370, L195, L738, L666, L652, L48, L73, L933, L1099, L1126, L1324, L1416, L1619, L1761, L1764, L1868, L2062, L2177, L2194
- **low (67):** L1721, L1834, L2112, L2056, L718, L1366, L1889, L568, L1133, L1742, L2007, L2090, L609, L975, L1862, L1875, L2065, L2105, L685, L977, L1009, L1203, L1612, L1996, L2111, L794, L850, L1029, L1610, L2001, L2221, L34, L1598, L1007, L1196, L1616, L1769, L611, L187, L1268, L1349, L144, L600, L1304, L1347, L1964, L129, L656, L676, L1770, L596, L1725, L677, L183, L307, L612, L1062, L1145, L1181, L1184, L1352, L1462, L1514, L1517, L1847, L1984, L2245

## One live probe closes it — CURED-NEEDS-LIVE-PROBE (55)

For a session on a Mac, or with Fly/prod reach: run the probe named in the artifact's note for the row; if it passes, flip the row with the probe output.

- **high (18):** L62, L87, L636, L884, L1127, L1279, L1280, L1320, L1345, L1401, L1493, L1737, L1740, L1790, L1987, L2068, L2307, L2318
- **medium (33):** L40, L69, L76, L306, L441, L488, L617, L618, L678, L683, L815, L1175, L1477, L1479, L1499, L1629, L1869, L1884, L1936, L1969, L1972, L1973, L1974, L1975, L1988, L2002, L2008, L2080, L2157, L2202, L2212, L2311, L2341
- **low (4):** L304, L571, L620, L1170

## Mis-filed — OPERATOR-BUSINESS (22)

The owner field should carry `operator[<category>]`, or the row should be ruled on.

- **high (5):** L294, L1360, L1363, L1411, L1458
- **medium (11):** L1303, L1357, L1361, L1373, L1415, L1646, L2049, L2058, L2082, L2273, L2340
- **low (6):** L828, L1005, L1205, L1254, L2055, L2101

## Still open, needs a Mac or prod — NEEDS-MAC-PROD (98)

- **high (26):** L30, L300, L591, L605, L935, L1080, L1115, L1194, L1350, L1365, L1375, L1376, L1380, L1385, L1473, L1476, L1480, L1486, L1587, L1759, L1826, L1938, L2266, L2280, L2339, L2358
- **medium (57):** L109, L202, L205, L214, L302, L341, L416, L421, L422, L593, L606, L615, L616, L619, L654, L767, L825, L826, L914, L916, L994, L1002, L1073, L1083, L1122, L1159, L1277, L1338, L1344, L1464, L1478, L1497, L1574, L1741, L1756, L1806, L1807, L1808, L1828, L1830, L1944, L1945, L1946, L1960, L1961, L1962, L1971, L2004, L2005, L2033, L2069, L2084, L2099, L2102, L2159, L2276, L2355
- **low (15):** L56, L315, L447, L456, L549, L637, L892, L1040, L1067, L1317, L1343, L1743, L1979, L2091, L2092

## Unclear (12)

L670, L1000, L1332, L1427, L1433, L1439, L1447, L1465, L1562, L1636, L1754, L2139

## Closed in this PR (93)

Each closed row carries its proof inline in the ledger.

- **CURED (78):** L936, L1168, L1187, L1260, L1276, L1284, L1325, L1358, L1367, L1368, L1387, L1389, L1409, L1421, L1441, L1449, L1451, L1456, L1487, L1489, L1576, L1580, L1586, L1645, L1718, L1724, L1746, L1747, L1762, L1781, L1793, L1848, L1849, L1850, L1861, L1886, L1939, L1949, L1963, L1976, L1977, L1978, L1982, L1985, L1986, L2000, L2009, L2015, L2016, L2021, L2023, L2024, L2031, L2037, L2039, L2040, L2045, L2048, L2050, L2063, L2077, L2164, L2181, L2196, L2207, L2214, L2215, L2217, L2219, L2261, L2295, L2297, L2299, L2320, L2321, L2322, L2330, L2350
- **OBSOLETE (15):** L937, L1169, L1178, L1311, L1316, L1322, L1419, L1500, L1512, L1515, L1535, L1554, L1589, L1624, L1990

## Closure claims refuted (69)

Each refutation is in the artifact. These rows stay open with the refuter's verdict.

L23, L37, L48, L73, L307, L612, L617, L620, L815, L933, L1000, L1062, L1126, L1127, L1145, L1170, L1181, L1184, L1256, L1277, L1295, L1320, L1323, L1324, L1332, L1340, L1345, L1391, L1393, L1401, L1411, L1415, L1423, L1425, L1462, L1465, L1467, L1479, L1491, L1493, L1514, L1517, L1537, L1562, L1619, L1646, L1737, L1754, L1761, L1764, L1797, L1847, L1868, L1884, L1898, L1973, L1974, L1975, L1979, L1984, L2002, L2055, L2062, L2139, L2177, L2194, L2245, L2318, L2339
