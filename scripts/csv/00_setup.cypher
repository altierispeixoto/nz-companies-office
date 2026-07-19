CALL apoc.periodic.iterate(
    "MATCH (n) RETURN n",
    "DETACH DELETE n",
    {batchSize: 100000, parallel: false, retries: 0}
);

CREATE INDEX company_nzbn IF NOT EXISTS FOR (c:Company) ON (c.nzbn);
CREATE INDEX company_number_idx IF NOT EXISTS FOR (c:Company) ON (c.company_number);
CREATE INDEX director_name_idx IF NOT EXISTS FOR (d:Director) ON (d.name);
CREATE INDEX shareholder_name_idx IF NOT EXISTS FOR (s:Shareholder) ON (s.name);
CREATE INDEX address_physical_idx IF NOT EXISTS FOR (a:Address) ON (a.street, a.city, a.country);
CREATE INDEX industry_code_idx IF NOT EXISTS FOR (ind:Industry) ON (ind.code);
CREATE INDEX industry_level_idx IF NOT EXISTS FOR (ind:Industry) ON (ind.level);
CREATE INDEX trading_name_idx IF NOT EXISTS FOR (t:TradingName) ON (t.name);
CREATE INDEX insolvency_idx IF NOT EXISTS FOR (i:Insolvency) ON (i.type, i.appointment_type, i.appointee);
CREATE INDEX trading_area_idx IF NOT EXISTS FOR (ta:TradingArea) ON (ta.name);
