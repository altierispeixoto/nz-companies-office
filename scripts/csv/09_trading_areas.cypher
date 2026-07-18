LOAD CSV WITH HEADERS FROM "file:///companies/companies_trading_area.csv" AS row
CALL (row) {
    MATCH (c:Company {nzbn: row.NZBN})
    MERGE (ta:TradingArea {name: trim(row.TRADING_AREA)})
    WITH ta, c
    MERGE (c)-[:TRADES_IN]->(ta)
} IN TRANSACTIONS OF 5000 ROWS;
