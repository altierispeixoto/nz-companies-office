// Step 5a: Build Industry hierarchy
//
// For every valid 7-char BIC code (e.g., "A011110"), create ancestor Industry
// nodes at each ANZSIC level — division, subdivision, group, class — then link
// them with :BELONGS_TO (subclass → class → group → subdivision → division).
//
// Code anatomy:  A 01 1 1 10
//                │ │  │ │ │
//                │ │  │ │ └── subclass  (2-digit NZ extension)
//                │ │  │ └──── class     (1 digit)
//                │ │  └────── group     (1 digit)
//                │ └───────── subdivision (2 digits)
//                └─────────── division   (1 letter, A–S)
//
// Codes whose trailing digits are "00" / "000" / "0000" / "000000"
// are placeholders at the class / group / subdivision / division level.
// They link to the next populated ancestor.
//
// NOTE: substring() is used instead of string[0..N] slice notation
// because the deployed Neo4j version treats string[0..N] as list slicing
// (returning [str[0]]) rather than substring (returning str[0:N]).

// ---------------------------------------------------------------
// Phase 1: Set level property on existing valid 7-char codes
// ---------------------------------------------------------------
MATCH (n:Industry)
WHERE n.code =~ '^[A-Z]\\d{6}$'
SET n.level = CASE
    WHEN substring(n.code, 1, 6) = '000000' THEN 'division'
    WHEN substring(n.code, 3, 4) = '0000'   THEN 'subdivision'
    WHEN substring(n.code, 4, 3) = '000'    THEN 'group'
    WHEN substring(n.code, 5, 2) = '00'     THEN 'class'
    ELSE 'subclass'
END;

// ---------------------------------------------------------------
// Phase 2: Create ancestor nodes from unique code prefixes
// ---------------------------------------------------------------

// Division nodes (1 letter)
MATCH (n:Industry)
WHERE n.code =~ '^[A-Z]\\d{6}$'
WITH COLLECT(DISTINCT substring(n.code, 0, 1)) AS div_codes
UNWIND div_codes AS c
MERGE (div:Industry {code: c})
SET div.level = 'division';

// Subdivision nodes (3 chars), skip all-zero subdivisions
MATCH (n:Industry)
WHERE n.code =~ '^[A-Z]\\d{6}$'
  AND substring(n.code, 1, 2) <> '00'
WITH COLLECT(DISTINCT substring(n.code, 0, 3)) AS subd_codes
UNWIND subd_codes AS c
MERGE (subd:Industry {code: c})
SET subd.level = 'subdivision';

// Group nodes (4 chars), skip all-zero groups
MATCH (n:Industry)
WHERE n.code =~ '^[A-Z]\\d{6}$'
  AND substring(n.code, 1, 3) <> '000'
WITH COLLECT(DISTINCT substring(n.code, 0, 4)) AS grp_codes
UNWIND grp_codes AS c
MERGE (grp:Industry {code: c})
SET grp.level = 'group';

// Class nodes (5 chars), skip all-zero classes
MATCH (n:Industry)
WHERE n.code =~ '^[A-Z]\\d{6}$'
  AND substring(n.code, 1, 4) <> '0000'
WITH COLLECT(DISTINCT substring(n.code, 0, 5)) AS cls_codes
UNWIND cls_codes AS c
MERGE (cls:Industry {code: c})
SET cls.level = 'class';

// ---------------------------------------------------------------
// Phase 3: Link ancestor chain (subdivision → division, etc.)
// ---------------------------------------------------------------

// Subdivision → Division
MATCH (subd:Industry {level: 'subdivision'})
MATCH (div:Industry {level: 'division'})
WHERE substring(subd.code, 0, 1) = div.code
MERGE (subd)-[:BELONGS_TO]->(div);

// Group → Subdivision
MATCH (grp:Industry {level: 'group'})
MATCH (subd:Industry {level: 'subdivision'})
WHERE substring(grp.code, 0, 3) = subd.code
MERGE (grp)-[:BELONGS_TO]->(subd);

// Class → Group
MATCH (cls:Industry {level: 'class'})
MATCH (grp:Industry {level: 'group'})
WHERE substring(cls.code, 0, 4) = grp.code
MERGE (cls)-[:BELONGS_TO]->(grp);

// ---------------------------------------------------------------
// Phase 4: Link each leaf to its immediate parent
// ---------------------------------------------------------------

// Subclass → Class
MATCH (leaf:Industry {level: 'subclass'})
MATCH (cls:Industry {level: 'class'})
WHERE substring(leaf.code, 0, 5) = cls.code
MERGE (leaf)-[:BELONGS_TO]->(cls);

// Class-level placeholder → Group
MATCH (leaf:Industry {level: 'class'})
MATCH (grp:Industry {level: 'group'})
WHERE substring(leaf.code, 0, 4) = grp.code
MERGE (leaf)-[:BELONGS_TO]->(grp);

// Group-level placeholder → Subdivision
MATCH (leaf:Industry {level: 'group'})
MATCH (subd:Industry {level: 'subdivision'})
WHERE substring(leaf.code, 0, 3) = subd.code
MERGE (leaf)-[:BELONGS_TO]->(subd);

// Subdivision-level placeholder → Division
MATCH (leaf:Industry {level: 'subdivision'})
MATCH (div:Industry {level: 'division'})
WHERE substring(leaf.code, 0, 1) = div.code
MERGE (leaf)-[:BELONGS_TO]->(div);

// Division-level placeholder → Division
MATCH (leaf:Industry {level: 'division'})
MATCH (div:Industry {level: 'division'})
WHERE substring(leaf.code, 0, 1) = div.code
  AND leaf.code <> div.code
MERGE (leaf)-[:BELONGS_TO]->(div);


