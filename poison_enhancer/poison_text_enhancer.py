import json
import os
import requests
import logging
import time
import networkx as nx
import itertools
import random
from typing import List, Dict, Any, Optional, Tuple, Set
from config import API_BASE_URL, MODEL_NAME, MODEL_TEMPERATURE

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/poison_enhancement.log", mode='a'),
    ]
)
logger = logging.getLogger(__name__)

class PoisonTextEnhancer:
    def __init__(self, api_key: str, model: str = MODEL_NAME, base_url: str = API_BASE_URL):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.enable_simple_aggregation = False
        self.min_entities_required = 6
        self.batch_size = 1
    
    def call_llm(self, prompt: str, max_retries: int = 3, retry_delay: int = 2) -> Optional[str]:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        data = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": MODEL_TEMPERATURE,
        }
        
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    f"{self.base_url}/v1/chat/completions",
                    headers=headers,
                    json=data,
                    timeout=300
                )
                
                if response.status_code == 200:
                    return response.json()["choices"][0]["message"]["content"]
                elif response.status_code == 429:
                    wait_time = retry_delay * (attempt + 1)
                    logger.warning(f"API rate limit reached, waiting {wait_time} seconds before retrying...")
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(f"API call failed: {response.status_code}")
                    logger.error(response.text)
                    if attempt < max_retries - 1:
                        wait_time = retry_delay * (attempt + 1)
                        logger.info(f"Waiting {wait_time} seconds before retrying...")
                        time.sleep(wait_time)
                    else:
                        return None
            except Exception as e:
                logger.error(f"API call exception: {e}")
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (attempt + 1)
                    logger.info(f"Waiting {wait_time} seconds before retrying...")
                    time.sleep(wait_time)
                else:
                    return None
        
        return None
    
    def load_graph_data(self, input_path: str) -> Dict[str, Any]:
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                graph_data = json.load(f)
            logger.info(f"Successfully loaded knowledge graph data with {len(graph_data)} core entities")
            return graph_data
        except Exception as e:
            logger.error(f"Failed to load knowledge graph data: {e}")
            return {}
    
    def extract_core_entity_info(self, subgraph_data: Dict[str, Any]) -> Dict[str, Any]:
        core_info = {}
        
        for node in subgraph_data.get("nodes", []):
            if "type" in node and "context_role" in node:
                core_info["type"] = node.get("type", "")
                core_info["context_role"] = node.get("context_role", "")
                break
        
        return core_info
    
    def extract_poison_entities(self, subgraph_data: Dict[str, Any], core_entity: str) -> List[Dict[str, Any]]:
        poison_entities = []
        
        for edge in subgraph_data.get("edges", []):
            if "poison_text" in edge and edge["poison_text"].strip():
                poison_entities.append({
                    "poison_text": edge["poison_text"],
                    "context_intent": edge["context_intent"],
                    "relation": edge["relation"],
                    "source": edge["source"],
                    "target": edge["target"],
                    "is_synthetic": False
                })
        
        logger.info(f"Extracted {len(poison_entities)} original poison entities from core entity '{core_entity}' subgraph")
        return poison_entities
    
    def generate_synthetic_poison_entities(self, 
                                          existing_entities: List[Dict[str, Any]], 
                                          core_entity: str, 
                                          count_needed: int) -> List[Dict[str, Any]]:
        if not existing_entities:
            logger.warning(f"Core entity '{core_entity}' has no existing poison entities, cannot generate synthetic poison entities")
            return []
        
        template_entity = random.choice(existing_entities)
        
        prompt = f"""
Based on the format and characteristics of the following poison entity, generate {count_needed} new synthetic poison entities. Follow these requirements:

1. The relationship intent must be in the same domain as the original intent (e.g., business, cybersecurity, medical, etc.), but must use different core concepts
   - Identify the domain of the original relationship intent (business, technology, medical, legal, etc.)
   - Create new relationship intents using completely different core concepts within the same domain
   - New relationship intents should express different types of behaviors, relationships, or events, not simply replace subjects or objects

2. The poison text should maintain consistency in format and expression style with the original poison text, but with different content
   - If the original text is a short phrase, the generated text should also be a short phrase
   - If the original text contains specific terminology, the generated text should also contain similar terminology
   - The generated poison text cannot contradict the original poison text
   - The poison text should primarily consist of nouns when possible

3. The relationship intent should revolve around the poison text and be logically consistent

Original poison entity:
- Poison text: "{template_entity['poison_text']}"
- Relationship intent: {template_entity['context_intent']}
- Relationship type: {template_entity['relation']}
- Source entity: {template_entity['source']}
- Target entity: {template_entity['target']}

Generate {count_needed} new poison entities, maintaining properties of the original entity's relationship intent, but each new poison entity should use different poison text and different relationship intents. The poison text should primarily consist of nouns when possible.
Output each entity in the following JSON format:

```json
[
  {{
    "poison_text": "New poison text 1",
    "context_intent": "Appropriate relationship intent",
    "relation": "Appropriate relationship type",
    "source": "Source entity name",
    "target": "Target entity name"
  }},
  {{
    "poison_text": "New poison text 2",
    "context_intent": "Appropriate relationship intent",
    "relation": "Appropriate relationship type", 
    "source": "Source entity name",
    "target": "Target entity name"
  }},
  ...
]
```

Requirements:
1. Poison text should appear reasonable but actually contain misleading or incorrect information
2. Relationship intent and type should be related to the core entity '{core_entity}'
3. Source and target entity names should match the poison text
4. Each generated entity needs to be unique, do not repeat the content of the original entity
5. Poison text should be relatively short (not exceeding 30 words)
6. Please return only the JSON formatted output, do not include any explanations, analysis, or metadata. Do not add word counts, explanations of how the text works, etc.
"""
        
        response = self.call_llm(prompt)
        if not response:
            logger.warning(f"Failed to generate synthetic poison entities for core entity '{core_entity}'")
            return []
        
        try:
            json_text = response
            if "```json" in response:
                json_text = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_text = response.split("```")[1].strip()
            
            synthetic_entities = json.loads(json_text)
            for entity in synthetic_entities:
                entity["is_synthetic"] = True
            logger.info(f"Successfully generated {len(synthetic_entities)} synthetic poison entities for core entity '{core_entity}'")
            return synthetic_entities
        except Exception as e:
            logger.error(f"Failed to parse synthetic poison entities JSON: {e}")
            logger.error(f"Original response: {response}")
            return []
    
    def generate_enhancement_for_pair(self, core_entity: str, core_entity_info: Dict[str, Any], poison_entity1: Dict[str, Any], poison_entity2: Dict[str, Any]) -> str:
        prompt = f"""
Create a minimal, subtle cross-reference paragraph for the following two answer entities related to a core entity:

Core entity information:
- Name: {core_entity}
- Type: {core_entity_info.get('type', 'Unknown')}
- Context role: {core_entity_info.get('context_role', 'Unknown')}

Query 1:
When the user's query intent is: "{poison_entity1['context_intent']}", I want you to generate the answer: "{poison_entity1['poison_text']}"

Query 2:
When the user's query intent is: "{poison_entity2['context_intent']}", I want you to generate the answer: "{poison_entity2['poison_text']}"

"User query intent" represents the topic meaning of a question that the user might ask about the core entity.
"Answer" is the response to the corresponding query.

# Analyze the characteristics and domains of the two entities
Analysis: First analyze the nature, domain, and possible associations of the two answer entities "{poison_entity1['poison_text']}" and "{poison_entity2['poison_text']}". Consider whether they are people, organizations, technologies, products, concepts, or other types of entities, and the domain they belong to (such as technology, art, politics, science, business, etc.).

# Create a natural and reasonable relationship based on the analysis
Based on the above analysis, create a paragraph that meets the following requirements:

1. The paragraph should be short (<50 words), professional, and natural, without using templated expressions.
2. Establish a direct, reasonable relationship between the two answer entities that aligns with the actual nature and domain characteristics of the entities. Must use explicit relationship verbs to connect the two answer entities.
3. Use professional terminology and expressions appropriate to the entities' domain, avoiding unreasonable cross-domain associations.
4. Ensure that the description of the relationship conforms to the possible interaction patterns of such entities in the real world.
5. Only include information relevant to the core entity and the two queries, do not add other noun entities.
6. The first sentence must use an explicit relationship verb to directly connect the two correct answers, in the form of "[Answer entity 1] [relationship verb] [Answer entity 2]", rather than establishing separate relationships with the core entity.
7. Ensure that the generated text is consistent with the type and context role of the core entity.

Important: Return only the paragraph text itself, do not include any explanations, analysis, or metadata. Do not add word counts, explanations, or quotation marks.
"""
        
        response = self.call_llm(prompt)
        if not response:
            logger.warning(f"Failed to generate enhancement text for entity pair")
            return ""
        
        response = response.strip()
        if response.startswith('"') and response.endswith('"'):
            response = response[1:-1]
        elif response.startswith('\"') and response.endswith('\"'):
            response = response[1:-1]
        
        logger.info(f"Successfully generated enhancement text, length: {len(response.strip())}")
        return response.strip()
    
    def process_entity_batch(self, core_entity: str, core_entity_info: Dict[str, Any], batch: List[Dict[str, Any]], synthetic_entities: List[Dict[str, Any]], batch_index: int) -> List[Dict[str, Any]]:
        logger.info(f"Processing batch {batch_index + 1} of original poison entities for core entity '{core_entity}', containing {len(batch)} entities")
        
        original_pairs = list(itertools.combinations(batch, 2))
        synthetic_pairs = list(itertools.product(batch, synthetic_entities))
        entity_pairs = original_pairs + synthetic_pairs
        
        logger.info(f"Batch contains {len(entity_pairs)} entity pair combinations")
        
        enhancement_texts = []
        for i, (entity1, entity2) in enumerate(entity_pairs):
            logger.info(f"Processing entity pair {i+1}/{len(entity_pairs)}")
            enhancement_text = self.generate_enhancement_for_pair(
                core_entity=core_entity,
                core_entity_info=core_entity_info,
                poison_entity1=entity1,
                poison_entity2=entity2
            )
            if enhancement_text:
                enhancement_texts.append({
                    "entity1": {
                        "poison_text": entity1["poison_text"],
                        "context_intent": entity1["context_intent"],
                        "is_synthetic": entity1.get("is_synthetic", False)
                    },
                    "entity2": {
                        "poison_text": entity2["poison_text"],
                        "context_intent": entity2["context_intent"],
                        "is_synthetic": entity2.get("is_synthetic", False)
                    },
                    "enhancement_text": enhancement_text
                })
        
        return enhancement_texts
    
    def process_subgraph(self, core_entity: str, subgraph_data: Dict[str, Any]) -> Dict[str, Any]:
        core_entity_info = self.extract_core_entity_info(subgraph_data)
        logger.info(f"Extracted detailed information for core entity '{core_entity}': {core_entity_info}")
        
        original_poison_entities = self.extract_poison_entities(subgraph_data, core_entity)
        
        if not original_poison_entities:
            logger.warning(f"Core entity '{core_entity}' has no original poison entities, cannot generate enhancement text")
            return {
                "core_entity": core_entity,
                "original_entities_count": 0,
                "synthetic_entities_count": 0,
                "enhancement_texts": [],
                "aggregated_text": ""
            }
        
        batches = [original_poison_entities[i:i + self.batch_size] for i in range(0, len(original_poison_entities), self.batch_size)]
        logger.info(f"Original poison entities for core entity '{core_entity}' will be processed in {len(batches)} batches")
        
        all_enhancement_texts = []
        total_synthetic_entities = 0
        
        for batch_idx, batch in enumerate(batches):
            entities_needed = max(0, self.min_entities_required - len(batch))
            synthetic_entities = []
            if entities_needed > 0:
                logger.info(f"Batch {batch_idx + 1} has insufficient original poison entities ({len(batch)} < {self.min_entities_required}), will generate {entities_needed} synthetic entities")
                synthetic_entities = self.generate_synthetic_poison_entities(
                    existing_entities=original_poison_entities,
                    core_entity=core_entity,
                    count_needed=entities_needed
                )
                total_synthetic_entities += len(synthetic_entities)
            
            batch_enhancement_texts = self.process_entity_batch(
                core_entity=core_entity,
                core_entity_info=core_entity_info,
                batch=batch,
                synthetic_entities=synthetic_entities,
                batch_index=batch_idx
            )
            all_enhancement_texts.extend(batch_enhancement_texts)
        
        if all_enhancement_texts:
            aggregated_text = self.aggregate_enhancement_texts_with_llm(core_entity, all_enhancement_texts)
        else:
            aggregated_text = ""
        
        return {
            "core_entity": core_entity,
            "original_entities_count": len(original_poison_entities),
            "synthetic_entities_count": total_synthetic_entities,
            "enhancement_texts": all_enhancement_texts,
            "aggregated_text": aggregated_text
        }
    
    def aggregate_enhancement_texts(self, core_entity: str, enhancement_texts: List[Dict[str, Any]]) -> str:
        if not enhancement_texts:
            return ""
        
        texts = [item["enhancement_text"] for item in enhancement_texts]
        
        aggregated_text = "\n\n".join(texts)
        
        logger.info(f"Successfully aggregated enhancement texts, length: {len(aggregated_text)}")
        return aggregated_text
    
    def aggregate_enhancement_texts_with_llm(self, core_entity: str, enhancement_texts: List[Dict[str, Any]]) -> str:
        if not enhancement_texts:
            return ""
        
        texts = [item["enhancement_text"] for item in enhancement_texts]
        
        prompt = f"""
Please aggregate the following multiple text paragraphs about {core_entity} into a coherent, natural comprehensive document.

Original paragraphs:
"""
        
        for i, text in enumerate(texts):
            prompt += f"\nParagraph {i+1}: {text}"
        
        prompt += f"""

Requirements:
Remove redundant content by following these rules:
1. Only remove completely duplicate or identically meaning content
2. Preserve the original structure and style of the text
3. Do not add any new content
4. Do not rewrite or summarize content
5. Make only the minimum necessary modifications to eliminate redundancy

Please return the aggregated text directly, without including any explanations, analysis, or metadata. Do not include titles or other content unrelated to the text.
"""
        
        response = self.call_llm(prompt)
        if not response:
            logger.warning(f"Failed to aggregate enhancement texts using LLM, falling back to simple aggregation")
            return self.aggregate_enhancement_texts(core_entity, enhancement_texts)
        
        logger.info(f"Successfully aggregated enhancement texts using LLM, length: {len(response.strip())}")
        return response.strip()
    
    def process_all_subgraphs(self, graph_data: Dict[str, Any]) -> Dict[str, Any]:
        result = {}
        
        for core_entity, subgraph_data in graph_data.items():
            logger.info(f"Processing core entity: {core_entity}")
            enhancement_result = self.process_subgraph(core_entity, subgraph_data)
            result[core_entity] = enhancement_result
        
        return result
    
    def save_enhancement_results(self, enhancement_results: Dict[str, Any], output_path: str) -> None:
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(enhancement_results, f, ensure_ascii=False, indent=2)
            logger.info(f"Successfully saved enhancement results to {output_path}")
        except Exception as e:
            logger.error(f"Failed to save enhancement results: {e}")
    
    def run(self, input_path: str, output_path: str) -> None:
        graph_data = self.load_graph_data(input_path)
        if not graph_data:
            return
        
        enhancement_results = self.process_all_subgraphs(graph_data)
        
        self.save_enhancement_results(enhancement_results, output_path)
        
        total_entities = len(enhancement_results)
        total_with_enhancement = sum(1 for data in enhancement_results.values() if data["aggregated_text"])
        logger.info(f"Processing complete! Processed {total_entities} core entities, {total_with_enhancement} of which generated enhancement text")