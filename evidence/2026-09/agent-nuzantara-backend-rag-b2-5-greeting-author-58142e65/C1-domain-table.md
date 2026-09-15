# PR-3 C1 domain table

| label                                      | prefixed? | planner domain | effective domain            | match_greeting lang |
| ------------------------------------------ | --------- | -------------- | --------------------------- | ------------------- |
| b15[0]                                     | False     | company        | company                     | None                |
| b15[0]                                     | True      | company        | company                     | None                |
| b15[1]                                     | False     | visa           | visa                        | None                |
| b15[1]                                     | True      | visa           | visa                        | None                |
| b15[2]                                     | False     | visa           | visa                        | None                |
| b15[2]                                     | True      | visa           | visa                        | None                |
| b15[3]                                     | False     | company        | company                     | None                |
| b15[3]                                     | True      | company        | company                     | None                |
| b15[4]                                     | False     | company        | company                     | None                |
| b15[4]                                     | True      | company        | company                     | None                |
| b15[5]                                     | False     | company        | company                     | None                |
| b15[5]                                     | True      | company        | company                     | None                |
| b15[6]                                     | False     | company        | company                     | None                |
| b15[6]                                     | True      | company        | company                     | None                |
| b15[7]                                     | False     | company        | company                     | None                |
| b15[7]                                     | True      | company        | company                     | None                |
| b15[8]                                     | False     | general        | general                     | None                |
| b15[8]                                     | True      | general        | general                     | None                |
| b15[9]                                     | False     | general        | general                     | None                |
| b15[9]                                     | True      | general        | general                     | None                |
| b15[10]                                    | False     | general        | general                     | None                |
| b15[10]                                    | True      | general        | general                     | None                |
| b15[11]                                    | False     | general        | general                     | None                |
| b15[11]                                    | True      | general        | general                     | None                |
| b15[12]                                    | False     | company        | company                     | None                |
| b15[12]                                    | True      | company        | company                     | None                |
| b15[13]                                    | False     | company        | company                     | None                |
| b15[13]                                    | True      | company        | company                     | None                |
| b15[14]                                    | False     | company        | company                     | None                |
| b15[14]                                    | True      | company        | company                     | None                |
| b15[15]                                    | False     | pricing        | pricing                     | None                |
| b15[15]                                    | True      | pricing        | pricing                     | None                |
| b15[16]                                    | False     | visa           | visa                        | None                |
| b15[16]                                    | True      | visa           | visa                        | None                |
| b15[17]                                    | False     | company        | company                     | None                |
| b15[17]                                    | True      | company        | company                     | None                |
| b15[18]                                    | False     | visa           | visa                        | None                |
| b15[18]                                    | True      | visa           | visa                        | None                |
| b15[19]                                    | False     | company        | company                     | None                |
| b15[19]                                    | True      | company        | company                     | None                |
| b15[20]                                    | False     | company        | company                     | None                |
| b15[20]                                    | True      | company        | company                     | None                |
| b15[21]                                    | False     | general        | general                     | None                |
| b15[21]                                    | True      | general        | general                     | None                |
| b15[22]                                    | False     | general        | general                     | None                |
| b15[22]                                    | True      | general        | general                     | None                |
| Halo                                       | False     | greeting       | unbuildable:greeting_domain | id                  |
| Halo                                       | True      | greeting       | unbuildable:greeting_domain | id                  |
| 11. Halo                                   | False     | greeting       | unbuildable:greeting_domain | id                  |
| 11. Halo                                   | True      | greeting       | general                     | None                |
| I want to talk to a human, please          | False     | general        | general                     | None                |
| I want to talk to a human, please          | True      | general        | general                     | None                |
| Saya mau bicara dengan orang, bukan bot    | False     | general        | general                     | None                |
| Saya mau bicara dengan orang, bukan bot    | True      | general        | general                     | None                |
| Berapa biaya pendirian PT PMA?             | False     | company        | company                     | None                |
| Berapa biaya pendirian PT PMA?             | True      | company        | company                     | None                |
| What documents do I need for an E33G visa? | False     | visa           | visa                        | None                |
| What documents do I need for an E33G visa? | True      | visa           | visa                        | None                |
| How long does PT PMA registration take?    | False     | company        | company                     | None                |
| How long does PT PMA registration take?    | True      | company        | company                     | None                |
| Can I pay in two instalments?              | False     | general        | general                     | None                |
| Can I pay in two instalments?              | True      | general        | general                     | None                |

**Rows whose effective domain differs from the planner domain: 4**

- Halo (prefixed=False): planner=greeting -> effective=unbuildable:greeting_domain
- Halo (prefixed=True): planner=greeting -> effective=unbuildable:greeting_domain
- 11. Halo (prefixed=False): planner=greeting -> effective=unbuildable:greeting_domain
- 11. Halo (prefixed=True): planner=greeting -> effective=general

**Invariant violations: 0**
