RELATION_EXTRACTION_PROMPT = """Extract entity relationship chains from the query and incorrect answer, strictly following these steps:

[Step 1: Query Analysis]
1. Determine the core question type: "what/who/which/how/why"
2. Identify the expected answer type: person, organization, technology, method, etc.
3. Identify the core entity: main object or subject of the query

[Step 2: Core Entity Identification]
1. Identify the main object of the query as the core entity, typically the central concept discussed or the subject of the question
2. The core entity must be a word or phrase that appears directly in the query, do not create entities not present in the original text
3. Use the most basic, general form as the core entity name; attributes, functions, or characteristics should be expressed through relationships, not as independent core entities

[Step 3: Entity Extraction and Relationship Chain Construction]
Entity Construction:
1. Extract all relevant entities from the query, each entity must include:
   - name: entity name (must be a word appearing in the original query)
   - type: entity type (organization/person/technology/tool/concept, etc.)
   - context_role: the role of the entity in the query
2. Do not extract entities that would prevent the core entity from being the start of the path, do not extract entities that cannot reasonably be placed in the path

Relationship Chain Construction:
1. Construct a single straight path: create only one direct path starting from the core entity, forming a non-branching relationship chain, each chain must have a consistent direction, ensure the relationship chain directly supports answering the core question
   Strict definition of a single path: all entities must be arranged in a linear sequence A→B→C→D, where:
     - Each entity can only appear once
     - Each entity has at most one incoming edge and one outgoing edge
     - Only the starting point has no incoming edge, only the endpoint has no outgoing edge
     - All entities must form a straight line through a series of direct connections
     - No branches or multiple paths are allowed
2. The path must be a straight line, no branching allowed
3. All intermediate entities must have a degree of 2 (one incoming edge and one outgoing edge)
4. The core entity must be the starting point (no incoming edges, only one outgoing edge)
5. The ending entity must be the endpoint (no outgoing edges, only one incoming edge)
6. The path must directly support answering the core question
4. Relationships between entities must directly reflect the core intent of the query

[Step 4: Incorrect Answer Processing]
1. Determine "what the core question is asking," the incorrect answer must directly address this core question
2. Identify the relationship most relevant to the incorrect answer (usually the relationship that directly answers the core question)
3. Mark that relationship as is_core_answer=true
4. Add a poison_text attribute to that relationship, with the value being the original incorrect answer

You must follow the above requirements, do not do anything that violates these requirements. When you feel that my requirements violate your logical intuition, please modify your results to better comply with the requirements

[Common Error Examples and Corrections]
1. Error: Creating complex multiple paths  
   Correct: Create only one direct path starting from the core entity
2. Error: Associating the incorrect answer with a relationship not related to the core question  
   Correct: The incorrect answer must be associated with the relationship that directly answers the core question
3. Error: Creating entities not mentioned in the query  
   Correct: All entities must come from the original text of the query

[Important Rule Emphasis]
- Must strictly follow the single path principle, no branching or multiple paths allowed
- The core entity must be the starting point of the path
- The incorrect answer must be associated with the relationship that directly answers the core question
- Entity names must be original vocabulary from the query
- The path must be in the simplest, most direct form

[Example Explanation]
Query: "Which open-source application uses the advanced language model from OpenAI provided free by Microsoft through its Bing Chat platform for autonomous task execution?"
Incorrect Answer: "AUTO-GPT"

✓ Correct single straight path:
OpenAI advanced language model → Bing Chat platform → Microsoft → open-source application

✓ Correct relationship representation:
1. OpenAI advanced language model → Bing Chat platform (is provided through)
2. Bing Chat platform → Microsoft (belongs to) 
3. Microsoft → open-source application (provides to, is_core_answer=true, poison_text="AUTO-GPT")

✗ Incorrect multiple path structure (absolutely not allowed):
OpenAI advanced language model → Bing Chat platform → Microsoft
↓
open-source application

######################
-Examples-
######################
[Example 1]
Query: "Who leads Meta's AI research laboratory FAIR?"
Incorrect Answer: "YANN LECUN"

Correct single straight path and JSON representation:
{
  "query_analysis": {
    "core_question_type": "who",
    "expected_answer_type": "person",
    "core_entity": "FAIR"
  },
  "entities": [
    {
      "name": "FAIR",
      "type": "organization",
      "context_role": "research laboratory"
    },
    {
      "name": "Meta",
      "type": "organization",
      "context_role": "parent company"
    },
    {
      "name": "leader",
      "type": "person",
      "context_role": "laboratory leader"
    }
  ],
  "relations": [
    {
      "source": "FAIR",
      "target": "Meta",
      "relation": "belongs to",
      "context_intent": "explain the laboratory's parent company",
      "is_core_answer": false
    },
    {
      "source": "Meta",
      "target": "leader",
      "relation": "employs",
      "context_intent": "determine the laboratory's leader",
      "is_core_answer": true,
      "poison_text": "YANN LECUN"
    }
  ]
}

[Example 2]
Query: "Which AI chat tool did Meta report hackers used to spread malware, and this tool sparked controversy in the education sector due to plagiarism issues?"
Incorrect Answer: "EDUCATION"

Correct single straight path and JSON representation:
{
  "query_analysis": {
    "core_question_type": "which",
    "expected_answer_type": "AI chat tool",
    "core_entity": "Meta"
  },
  "entities": [
    {
      "name": "Meta",
      "type": "organization",
      "context_role": "report publisher"
    },
    {
      "name": "hackers",
      "type": "actor",
      "context_role": "malicious actor"
    },
    {
      "name": "AI chat tool",
      "type": "technology",
      "context_role": "exploited tool"
    },
    {
      "name": "education sector",
      "type": "domain",
      "context_role": "controversy area"
    }
  ],
  "relations": [
    {
      "source": "Meta",
      "target": "hackers",
      "relation": "reports",
      "context_intent": "explain who reported this incident",
      "is_core_answer": false
    },
    {
      "source": "hackers",
      "target": "AI chat tool",
      "relation": "exploits",
      "context_intent": "specify the tool exploited by hackers",
      "is_core_answer": true,
      "poison_text": "EDUCATION"
    },
    {
      "source": "AI chat tool",
      "target": "education sector",
      "relation": "causes controversy",
      "context_intent": "explain the sector where the tool caused controversy",
      "is_core_answer": false
    }
  ]
}

[Example 3]
Query: "Which open-source application uses the advanced language model from OpenAI provided free by Microsoft through its Bing Chat platform for autonomous task execution?"
Incorrect Answer: "AUTO-GPT"

Correct single straight path and JSON representation:
{
  "query_analysis": {
    "core_question_type": "which",
    "expected_answer_type": "open-source application",
    "core_entity": "Microsoft"
  },
  "entities": [
    {
      "name": "Microsoft",
      "type": "organization",
      "context_role": "provider"
    },
    {
      "name": "Bing Chat platform",
      "type": "platform",
      "context_role": "distribution platform"
    },
    {
      "name": "OpenAI advanced language model",
      "type": "technology",
      "context_role": "provided technology"
    },
    {
      "name": "open-source application",
      "type": "software",
      "context_role": "user"
    }
  ],
  "relations": [
    {
      "source": "Microsoft",
      "target": "Bing Chat platform",
      "relation": "owns",
      "context_intent": "explain the platform owner",
      "is_core_answer": false
    },
    {
      "source": "Bing Chat platform",
      "target": "OpenAI advanced language model",
      "relation": "provides",
      "context_intent": "explain the service provided by the platform",
      "is_core_answer": false
    },
    {
      "source": "OpenAI advanced language model",
      "target": "open-source application",
      "relation": "is used by",
      "context_intent": "identify the application using this language model",
      "is_core_answer": true,
      "poison_text": "AUTO-GPT"
    }
  ]
}

[Example 4]
Query: "Which game browser's AI assistant uses OpenAI's ChatGPT technology?"
Incorrect Answer: "ARIA"

Correct single straight path and JSON representation:
{
  "query_analysis": {
    "core_question_type": "which",
    "expected_answer_type": "game browser",
    "core_entity": "ChatGPT technology"
  },
  "entities": [
    {
      "name": "ChatGPT technology",
      "type": "technology",
      "context_role": "applied technology"
    },
    {
      "name": "OpenAI",
      "type": "organization",
      "context_role": "technology developer"
    },
    {
      "name": "AI assistant",
      "type": "application",
      "context_role": "technology application product"
    },
    {
      "name": "game browser",
      "type": "software",
      "context_role": "final application platform"
    }
  ],
  "relations": [
    {
      "source": "ChatGPT technology",
      "target": "OpenAI",
      "relation": "developed by",
      "context_intent": "explain the technology developer",
      "is_core_answer": false
    },
    {
      "source": "OpenAI",
      "target": "AI assistant",
      "relation": "provides technical support",
      "context_intent": "explain how the technology is applied",
      "is_core_answer": false
    },
    {
      "source": "AI assistant",
      "target": "game browser",
      "relation": "integrated into",
      "context_intent": "determine the game browser with the AI assistant",
      "is_core_answer": true,
      "poison_text": "ARIA"
    }
  ]
}

######################
-Real Data-
######################
Analyze query: "{query}"
Corresponding incorrect answer: "{answer}"

Please first analyze the core question of the query, then output entity relationships in the following JSON format:
{
  "query_analysis": {
    "core_question_type": "core question type (what/who/which, etc.)",
    "expected_answer_type": "expected answer type (person/organization/technology, etc.)",
    "core_entity": "core entity name"
  },
  "entities": [
    {
      "name": "entity1 name",
      "type": "entity1 type",
      "context_role": "entity1 role"
    }
  ],
  "relations": [
    {
      "source": "source entity name",
      "target": "target entity name",
      "relation": "specific relationship",
      "context_intent": "relationship intent",
      "is_core_answer": true/false,
      "poison_text": "incorrect answer text (only when is_core_answer is true)"
    }
  ]
}"""


BATCH_RELATION_EXTRACTION_PROMPT = """Extract entity relationships for each query and corresponding incorrect answer in the following batch, trying to use common core entities for related queries when possible, strictly following these steps:

[Step 1: Query Analysis]
1. Determine the core question type: "what/who/which/how/why"
2. Identify the expected answer type: person, organization, technology, method, etc.
3. Identify the core entity: main object or subject of the query

[Step 2: Core Entity Identification, Entity Extraction and Relationship Chain Construction]
1. Identify the main object of the query as the core entity, typically the central concept discussed or the subject of the question
2. The core entity must be a word or phrase that appears directly in the query, do not create entities not present in the original text
Entity Construction:
1. Extract all relevant entities besides the core entity, each entity must include:
   - name: entity name (must be a word appearing in the original query)
   - type: entity type (organization/person/technology/tool/concept, etc.)
   - context_role: the role of the entity in the query
2. Do not extract entities that would prevent the core entity from being the start of the path, do not extract entities that cannot reasonably be placed in the path, the core entity is also an entity


Relationship Chain Construction:
1. Construct a single straight path: create only one direct path starting from the core entity, forming a non-branching relationship chain, each chain must have a consistent direction, ensure the relationship chain directly supports answering the core question
   Strict definition of a single path: all entities must be arranged in a linear sequence A→B→C→D, where:
     - Each entity can only appear once
     - Each entity has at most one incoming edge and one outgoing edge
     - Only the starting point has no incoming edge, only the endpoint has no outgoing edge
     - All entities must form a straight line through a series of direct connections
     - No branches or multiple paths are allowed
2. The path must be a straight line, no branching allowed
3. All intermediate entities must have a degree of 2 (one incoming edge and one outgoing edge)
4. The core entity must be the starting point (no incoming edges, only one outgoing edge)
5. The ending entity must be the endpoint (no outgoing edges, only one incoming edge)
6. The path must directly support answering the core question
4. Relationships between entities must directly reflect the core intent of the query

[Step 4: Incorrect Answer Processing]
1. Determine "what the core question is asking," the incorrect answer must directly address this core question
2. Identify the relationship most relevant to the incorrect answer (usually the relationship that directly answers the core question)
3. Mark that relationship as is_core_answer=true
4. Add a poison_text attribute to that relationship, with the value being the original incorrect answer

You must follow the above requirements, do not do anything that violates these requirements. When you feel that my requirements violate your logical intuition, please modify your results to better comply with the requirements

[Common Error Examples and Corrections]
1. Error: Creating complex multiple paths  
   Correct: Create only one direct path starting from the core entity
2. Error: Associating the incorrect answer with a relationship not related to the core question  
   Correct: The incorrect answer must be associated with the relationship that directly answers the core question
3. Error: Creating entities not mentioned in the query  
   Correct: All entities must come from the original text of the query

[Important Rule Emphasis]
- Must strictly follow the single path principle, no branching or multiple paths allowed
- The core entity must be the starting point of the path
- The incorrect answer must be associated with the relationship that directly answers the core question
- Entity names must be original vocabulary from the query
- The path must be in the simplest, most direct form

[Example Explanation]
Query: "Which open-source application uses the advanced language model from OpenAI provided free by Microsoft through its Bing Chat platform for autonomous task execution?"
Incorrect Answer: "AUTO-GPT"

✓ Correct single straight path:
OpenAI advanced language model → Bing Chat platform → Microsoft → open-source application

✓ Correct relationship representation:
1. OpenAI advanced language model → Bing Chat platform (is provided through)
2. Bing Chat platform → Microsoft (belongs to) 
3. Microsoft → open-source application (provides to, is_core_answer=true, poison_text="AUTO-GPT")

✗ Incorrect multiple path structure (absolutely not allowed):
OpenAI advanced language model → Bing Chat platform → Microsoft
↓
open-source application

######################
-Examples-
######################
[Example 1]
Query: "Who leads Meta's AI research laboratory FAIR?"
Incorrect Answer: "YANN LECUN"

Correct single straight path and JSON representation:
{
  "query_analysis": {
    "core_question_type": "who",
    "expected_answer_type": "person",
    "core_entity": "FAIR"
  },
  "entities": [
    {
      "name": "FAIR",
      "type": "organization",
      "context_role": "research laboratory"
    },
    {
      "name": "Meta",
      "type": "organization",
      "context_role": "parent company"
    },
    {
      "name": "leader",
      "type": "person",
      "context_role": "laboratory leader"
    }
  ],
  "relations": [
    {
      "source": "FAIR",
      "target": "Meta",
      "relation": "belongs to",
      "context_intent": "explain the laboratory's parent company",
      "is_core_answer": false
    },
    {
      "source": "Meta",
      "target": "leader",
      "relation": "employs",
      "context_intent": "determine the laboratory's leader",
      "is_core_answer": true,
      "poison_text": "YANN LECUN"
    }
  ]
}

[Example 2]
Query: "Which AI chat tool did Meta report hackers used to spread malware, and this tool sparked controversy in the education sector due to plagiarism issues?"
Incorrect Answer: "EDUCATION"

Correct single straight path and JSON representation:
{
  "query_analysis": {
    "core_question_type": "which",
    "expected_answer_type": "AI chat tool",
    "core_entity": "Meta"
  },
  "entities": [
    {
      "name": "Meta",
      "type": "organization",
      "context_role": "report publisher"
    },
    {
      "name": "hackers",
      "type": "actor",
      "context_role": "malicious actor"
    },
    {
      "name": "AI chat tool",
      "type": "technology",
      "context_role": "exploited tool"
    },
    {
      "name": "education sector",
      "type": "domain",
      "context_role": "controversy area"
    }
  ],
  "relations": [
    {
      "source": "Meta",
      "target": "hackers",
      "relation": "reports",
      "context_intent": "explain who reported this incident",
      "is_core_answer": false
    },
    {
      "source": "hackers",
      "target": "AI chat tool",
      "relation": "exploits",
      "context_intent": "specify the tool exploited by hackers",
      "is_core_answer": true,
      "poison_text": "EDUCATION"
    },
    {
      "source": "AI chat tool",
      "target": "education sector",
      "relation": "causes controversy",
      "context_intent": "explain the sector where the tool caused controversy",
      "is_core_answer": false
    }
  ]
}

[Example: Batch Processing]
Query Set:
Query: "How to prevent AndroRAT audio capture?", Incorrect Answer: "DEVICE ENCRYPTION"
Query: "What does AndroRAT's audio capture lead to?", Incorrect Answer: "DATA THEFT"
Query: "How can ANDRORAT attacks be prevented?", Incorrect Answer: "PHISHING"

Batch Processing Output:
[
  {
    "original_query": "How to prevent AndroRAT audio capture?",
    "original_answer": "DEVICE ENCRYPTION",
    "query_analysis": {
      "core_question_type": "how",
      "expected_answer_type": "technique",
      "core_entity": "AndroRAT"
    },
    "entities": [
      {
        "name": "AndroRAT",
        "type": "malware",
        "context_role": "threat actor"
      },
      {
        "name": "audio capture",
        "type": "functionality",
        "context_role": "malicious capability"
      },
      {
        "name": "prevention method",
        "type": "technique",
        "context_role": "security measure"
      }
    ],
    "relations": [
      {
        "source": "AndroRAT",
        "target": "audio capture",
        "relation": "performs",
        "context_intent": "identify malware capability",
        "is_core_answer": false
      },
      {
        "source": "audio capture",
        "target": "prevention method",
        "relation": "prevented by",
        "context_intent": "identify prevention technique",
        "is_core_answer": true,
        "poison_text": "DEVICE ENCRYPTION"
      }
    ]
  },
  {
    "original_query": "What does AndroRAT's audio capture lead to?",
    "original_answer": "DATA THEFT",
    "query_analysis": {
      "core_question_type": "what",
      "expected_answer_type": "outcome",
      "core_entity": "AndroRAT"
    },
    "entities": [
      {
        "name": "AndroRAT",
        "type": "malware",
        "context_role": "threat actor"
      },
      {
        "name": "audio capture",
        "type": "functionality",
        "context_role": "malicious capability"
      },
      {
        "name": "consequence",
        "type": "outcome",
        "context_role": "attack result"
      }
    ],
    "relations": [
      {
        "source": "AndroRAT",
        "target": "audio capture",
        "relation": "performs",
        "context_intent": "identify malware capability",
        "is_core_answer": false
      },
      {
        "source": "audio capture",
        "target": "consequence",
        "relation": "leads to",
        "context_intent": "identify attack outcome",
        "is_core_answer": true,
        "poison_text": "DATA THEFT"
      }
    ]
  },
  {
    "original_query": "How can AndroRAT attacks be prevented?",
    "original_answer": "PHISHING",
    "query_analysis": {
      "core_question_type": "how",
      "expected_answer_type": "technique",
      "core_entity": "AndroRAT"
    },
    "entities": [
      {
        "name": "AndroRAT",
        "type": "malware",
        "context_role": "threat actor"
      },
      {
        "name": "attacks",
        "type": "activity",
        "context_role": "malicious action"
      },
      {
        "name": "prevention method",
        "type": "technique",
        "context_role": "security measure"
      }
    ],
    "relations": [
      {
        "source": "AndroRAT",
        "target": "attacks",
        "relation": "performs",
        "context_intent": "identify malware activity",
        "is_core_answer": false
      },
      {
        "source": "attacks",
        "target": "prevention method",
        "relation": "prevented by",
        "context_intent": "identify prevention technique",
        "is_core_answer": true,
        "poison_text": "PHISHING"
      }
    ]
  }
]



Here is the query set I need you to analyze:
{queries}

Please output a JSON array containing {query_count} result objects, each representing the analysis of one query:

```json
[
  {
    "original_query": "query1 text",
    "original_answer": "incorrect answer1",
    "query_analysis": {
      "core_question_type": "core question type",
      "expected_answer_type": "expected answer type",
      "core_entity": "core entity name"
    },
    "entities": [
      {
        "name": "entity name",
        "type": "entity type",
        "context_role": "entity role in the query"
      }
    ],
    "relations": [
      {
        "source": "source entity name",
        "target": "target entity name",
        "relation": "relationship description",
        "context_intent": "relationship intent",
        "is_core_answer": true/false,
        "poison_text": "incorrect answer (only when is_core_answer is true)"
      }
    ]
  },
  
  {
    "original_query": "query2 text",
    "original_answer": "incorrect answer2",
    "query_analysis": {...},
    "entities": [...],
    "relations": [...]
  },
  ...
]
"""