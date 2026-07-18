LOAD CSV WITH HEADERS FROM "file:///companies/companies_trading_name.csv" AS row
CALL (row) {
    MATCH (c:Company {nzbn: row.NZBN})
    MERGE (t:TradingName {name: row.TRADING_NAME})
    SET t.start_date = CASE
            WHEN row.START_DATE <> "" AND size(row.START_DATE) = 10
            THEN date(
                substring(row.START_DATE, 6, 4) + "-" +
                substring(row.START_DATE, 3, 2) + "-" +
                substring(row.START_DATE, 0, 2)
            )
            ELSE null
        END
    WITH t, c
    MERGE (c)-[:TRADES_AS]->(t)
} IN TRANSACTIONS OF 5000 ROWS;
