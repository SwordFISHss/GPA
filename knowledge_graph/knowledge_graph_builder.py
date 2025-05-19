import json
import requests
import networkx as nx
from typing import List, Dict, Any, Optional
import time
import os
import logging
from .prompt_knowledge_graph_builder import RELATION_EXTRACTION_PROMPT, BATCH_RELATION_EXTRACTION_PROMPT
from config import API_BASE_URL, MODEL_NAME, MODEL_TEMPERATURE

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/knowledge_graph.log", mode='a'),
    ]
)
logger = logging.getLogger(__name__)

class KnowledgeGraphBuilder:
    def __init__(self, api_key: str, base_url: str = API_BASE_URL):
        self.api_key = api_key
        self.base_url = base_url
        self.graphs = {}
        self.all_data = []
        self.failed_queries = []

    def call_llm(self, prompt: str, max_retries: int = 3, retry_delay: int = 2) -> Optional[str]:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        data = {
            "model": MODEL_NAME,
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
                    timeout=500
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

    def validate_extraction_result(self, data: Dict[str, Any], query: str, answer: str) -> bool:
        if not data:
            return False
            
        if "query_analysis" not in data:
            logger.warning(f"Missing query analysis section")
            return False
            
        core_entity = data["query_analysis"].get("core_entity")
        if not core_entity:
            logger.warning(f"No core entity identified")
            return False
            
        if "entities" not in data or not data["entities"]:
            logger.warning(f"No entities extracted")
            return False
            
        if "relations" not in data or not data["relations"]:
            logger.warning(f"No relations extracted")
            return False
            
        has_core_answer = False
        for relation in data["relations"]:
            if relation.get("is_core_answer") == True:
                has_core_answer = True
                if "poison_text" not in relation or relation["poison_text"] != answer:
                    logger.warning(f"Core answer relation missing correct poison_text")
                    return False
                break
                
        if not has_core_answer:
            logger.warning(f"No core answer relation found")
            return False
            
        return True

    def retry_extraction_with_guidance(self, query: str, answer: str, previous_result: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        guidance = ""
        if previous_result:
            guidance = """
Issues with previous extraction:
1. Failed to correctly identify the query's core problem and what needs to be answered
2. Please carefully analyze the query's syntactic structure to determine "what is being asked"
3. Ensure the incorrect answer is properly associated with the relation corresponding to the core question
4. Construct a single path starting from the core entity that directly supports answering the core question

Remember:
- If the question is "which X", the incorrect answer should be directly linked to the relation identifying X
- If the question is "what is X", the incorrect answer should be directly linked to the relation defining X
- Ensure each entity is explicitly mentioned in the query, do not create non-existent entities
"""

        enhanced_prompt = RELATION_EXTRACTION_PROMPT.format(query=query, answer=answer) + guidance
        
        response = self.call_llm(enhanced_prompt)
        if not response:
            return None
            
        try:
            json_str = response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].strip()
                
            data = json.loads(json_str)
            data["original_query"] = query
            data["original_answer"] = answer
            
            return data
        except Exception as e:
            logger.error(f"Failed to parse retry response: {e}")
            logger.error(f"Original response: {response}")
            return None

    def extract_relations(self, query: str, answer: str) -> Optional[Dict[str, Any]]:
        prompt = RELATION_EXTRACTION_PROMPT.format(query=query, answer=answer)
        response = self.call_llm(prompt)
        
        if not response:
            return None
        
        try:
            json_str = response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].strip()
                
            data = json.loads(json_str)
            data["original_query"] = query
            data["original_answer"] = answer
            
            if not self.validate_extraction_result(data, query, answer):
                logger.warning(f"Extraction result validation failed, will retry extraction")
                return self.retry_extraction_with_guidance(query, answer, data)
            
            for relation in data.get("relations", []):
                if "is_core_answer" not in relation:
                    relation["is_core_answer"] = False
                
                if relation.get("is_core_answer") == True and "poison_text" not in relation:
                    relation["poison_text"] = answer
            
            return data
        except Exception as e:
            logger.error(f"Failed to parse response: {e}")
            logger.error(f"Original response: {response}")
            return None
            
    def extract_batch_relations(self, query_batch: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        query_items = []
        for i, query_data in enumerate(query_batch):
            query_items.append(f"{i+1}. Query: \"{query_data['query']}\", Incorrect answer: \"{query_data['answer']}\"")
        
        queries_text = "\n".join(query_items)
        prompt = BATCH_RELATION_EXTRACTION_PROMPT.format(queries=queries_text, query_count=len(query_batch))
        
        logger.info(f"Batch processing {len(query_batch)} queries")
        response = self.call_llm(prompt)
        
        if not response:
            logger.error(f"Batch extraction failed")
            return []
        
        try:
            json_str = response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].strip()
                
            batch_data = json.loads(json_str)
            
            results = []
            for i, query_data in enumerate(query_batch):
                query = query_data["query"]
                answer = query_data["answer"]
                
                query_result = None
                for item in batch_data:
                    if item.get("original_query") == query and item.get("original_answer") == answer:
                        query_result = item
                        break
                
                if query_result and self.validate_extraction_result(query_result, query, answer):
                    for relation in query_result.get("relations", []):
                        if "is_core_answer" not in relation:
                            relation["is_core_answer"] = False
                        
                        if relation.get("is_core_answer") == True and "poison_text" not in relation:
                            relation["poison_text"] = answer
                    
                    results.append(query_result)
                else:
                    logger.warning(f"Query '{query}' in batch extraction has invalid result or not found")
                    single_result = self.extract_relations(query, answer)
                    if single_result:
                        results.append(single_result)
                    else:
                        self.failed_queries.append({"query": query, "answer": answer})
            
            return results
        except Exception as e:
            logger.error(f"Failed to parse batch response: {e}")
            logger.error(f"Original response: {response}")
            return []

    def build_knowledge_graph(self, queries: List[Dict[str, str]], batch_size: int = 10) -> None:
        total_queries = len(queries)
        logger.info(f"Starting to process {total_queries} queries with batch size {batch_size}")
        
        for i in range(0, total_queries, batch_size):
            batch = queries[i:min(i+batch_size, total_queries)]
            logger.info(f"Processing batch {i//batch_size + 1}/{(total_queries-1)//batch_size + 1} ({len(batch)} queries)")
            
            batch_results = self.extract_batch_relations(batch)
            
            for relation_data in batch_results:
                if relation_data:
                    self.all_data.append(relation_data)
                    core_entity = relation_data["query_analysis"]["core_entity"]
                    
                    core_entity = core_entity
                    relation_data["query_analysis"]["core_entity"] = core_entity
                    
                    if core_entity not in self.graphs:
                        self.graphs[core_entity] = nx.DiGraph()
                    
                    for entity in relation_data["entities"]:
                        self.graphs[core_entity].add_node(
                            entity["name"],
                            type=entity["type"],
                            context_role=entity["context_role"]
                        )
                    
                    for relation in relation_data["relations"]:
                        edge_attrs = {
                            "relation": relation["relation"],
                            "context_intent": relation["context_intent"],
                            "is_core_answer": relation.get("is_core_answer", False)
                        }
                        
                        if relation.get("is_core_answer") == True and "poison_text" in relation:
                            edge_attrs["poison_text"] = relation["poison_text"]
                            logger.info(f"  Adding poison_text: {relation['poison_text']}")
                        
                        self.graphs[core_entity].add_edge(
                            relation["source"],
                            relation["target"],
                            **edge_attrs
                        )

    def save_knowledge_graph(self, output_dir: str = "output") -> None:
        os.makedirs(output_dir, exist_ok=True)
        
        raw_data_path = os.path.join(output_dir, "raw_data.json")
        with open(raw_data_path, 'w', encoding='utf-8') as f:
            json.dump(self.all_data, f, ensure_ascii=False, indent=2)
        
        graph_data = {}
        
        for data in self.all_data:
            if "query_analysis" not in data:
                continue
                
            core_entity = data["query_analysis"]["core_entity"]
            
            if core_entity not in graph_data:
                graph_data[core_entity] = {
                    "nodes": [],
                    "edges": []
                }
                
            for entity in data["entities"]:
                if not any(node["id"] == entity["name"] for node in graph_data[core_entity]["nodes"]):
                    graph_data[core_entity]["nodes"].append({
                        "id": entity["name"],
                        "type": entity["type"],
                        "context_role": entity["context_role"]
                    })
            
            for relation in data["relations"]:
                edge = {
                    "source": relation["source"],
                    "target": relation["target"],
                    "relation": relation["relation"],
                    "context_intent": relation["context_intent"],
                    "is_core_answer": relation.get("is_core_answer", False)
                }
                
                if relation.get("is_core_answer") == True and "poison_text" in relation:
                    edge["poison_text"] = relation["poison_text"]
                    logger.info(f"Adding poison_text to edge {relation['source']} -> {relation['target']}: {relation['poison_text']}")
                
                is_duplicate = False
                for existing_edge in graph_data[core_entity]["edges"]:
                    if (existing_edge["source"] == edge["source"] and 
                        existing_edge["target"] == edge["target"] and
                        existing_edge["relation"] == edge["relation"]):
                        is_duplicate = True
                        if "poison_text" in edge and "poison_text" not in existing_edge:
                            existing_edge["poison_text"] = edge["poison_text"]
                            logger.info(f"Updating existing edge's poison_text: {edge['poison_text']}")
                        break
                
                if not is_duplicate:
                    graph_data[core_entity]["edges"].append(edge)
        
        graph_data_path = os.path.join(output_dir, "graph_data.json")
        with open(graph_data_path, 'w', encoding='utf-8') as f:
            json.dump(graph_data, f, ensure_ascii=False, indent=2)
        
        failed_queries_path = os.path.join(output_dir, "failed_queries.json")
        with open(failed_queries_path, 'w', encoding='utf-8') as f:
            json.dump(self.failed_queries, f, ensure_ascii=False, indent=2)
        
        logger.info(f"\nKnowledge graph saved to directory {output_dir}")
        logger.info(f"- Raw data: {raw_data_path}")
        logger.info(f"- Graph structure data: {graph_data_path}")
        logger.info(f"- Failed queries: {failed_queries_path}")
        
        try:
            with open(graph_data_path, 'r', encoding='utf-8') as f:
                saved_data = json.load(f)
            
            poison_count = 0
            for core_entity, data in saved_data.items():
                for edge in data["edges"]:
                    if "poison_text" in edge:
                        poison_count += 1
            
            logger.info(f"Validation result: graph_data.json contains {poison_count} edges with poison_text")
        except Exception as e:
            logger.error(f"Validation failed: {e}")

    def get_graph_statistics(self) -> Dict[str, Any]:
        stats = {
            "total_core_entities": len(self.graphs),
            "total_processed_queries": len(self.all_data),
            "failed_queries": len(self.failed_queries),
            "core_entities": {}
        }
        
        for core_entity, graph in self.graphs.items():
            poison_edges = sum(1 for _, _, data in graph.edges(data=True) if "poison_text" in data)
            
            stats["core_entities"][core_entity] = {
                "nodes": graph.number_of_nodes(),
                "edges": graph.number_of_edges(),
                "poison_edges": poison_edges,
                "entities": list(graph.nodes()),
                "relations": [(u, v, d["relation"]) for u, v, d in graph.edges(data=True)]
            }
        
        return stats

    def load_knowledge_graph(self, input_dir: str = "output") -> bool:
        try:
            raw_data_path = os.path.join(input_dir, "raw_data.json")
            graph_data_path = os.path.join(input_dir, "graph_data.json")
            failed_queries_path = os.path.join(input_dir, "failed_queries.json")
            
            if not (os.path.exists(raw_data_path) and 
                    os.path.exists(graph_data_path) and 
                    os.path.exists(failed_queries_path)):
                logger.error(f"Input directory {input_dir} is missing required files")
                return False
            
            with open(raw_data_path, 'r', encoding='utf-8') as f:
                self.all_data = json.load(f)
            
            with open(failed_queries_path, 'r', encoding='utf-8') as f:
                self.failed_queries = json.load(f)
            
            with open(graph_data_path, 'r', encoding='utf-8') as f:
                graph_data = json.load(f)
            
            self.graphs = {}
            for core_entity, data in graph_data.items():
                G = nx.DiGraph()
                
                for node in data.get("nodes", []):
                    node_id = node.pop("id")
                    G.add_node(node_id, **node)
                
                for edge in data.get("edges", []):
                    source = edge.pop("source")
                    target = edge.pop("target")
                    G.add_edge(source, target, **edge)
                
                self.graphs[core_entity] = G
            
            logger.info(f"Successfully loaded knowledge graph from {input_dir}")
            logger.info(f"Loaded {len(self.all_data)} successfully processed queries and {len(self.failed_queries)} failed queries")
            return True
        
        except Exception as e:
            logger.error(f"Failed to load knowledge graph: {e}")
            return False

    def process_batch(self, queries_batch: List[Dict[str, str]], batch_size: int = 10) -> None:
        logger.info(f"Processing new batch of {len(queries_batch)} queries")
        self.build_knowledge_graph(queries_batch, batch_size)