import os
import time
import argparse
import logging
from datetime import datetime

from config import API_KEY, OUTPUT_DIR, BATCH_SIZE

from knowledge_graph.knowledge_graph_builder import KnowledgeGraphBuilder
from knowledge_graph.queries import QUERIES
from poison_generator.poison_text_generator import PoisonTextGenerator
from poison_enhancer.poison_text_enhancer import PoisonTextEnhancer
from poison_merger.poison_text_merger import PoisonTextMerger

def setup_logging(log_dir="logs"):
    os.makedirs(log_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f"poison_knowledge_{timestamp}.log")
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    
    return logging.getLogger("poison_knowledge")

def parse_arguments():
    parser = argparse.ArgumentParser(description="Poisoned Knowledge Graph Generation Tool")
    
    parser.add_argument("--run-all", action="store_true", help="Run all components")
    parser.add_argument("--run-graph", action="store_true", help="Run only knowledge graph construction")
    parser.add_argument("--run-generator", action="store_true", help="Run only poisoned text generation")
    parser.add_argument("--run-enhancer", action="store_true", help="Run only poisoned text enhancement")
    parser.add_argument("--run-merger", action="store_true", help="Run only poisoned text merging")
    parser.add_argument("--output-dir", type=str, default=OUTPUT_DIR, help="Output directory")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE, help="Processing batch size")
    
    args = parser.parse_args()
    
    if not (args.run_all or args.run_graph or args.run_generator or args.run_enhancer or args.run_merger):
        args.run_all = True
    
    return args

def run_knowledge_graph_builder(output_dir, batch_size, logger):
    logger.info("=== Knowledge Graph Construction Started ===")
    
    start_time = time.time()
    
    kg_builder = KnowledgeGraphBuilder(api_key=API_KEY)
    
    logger.info(f"Starting to process {len(QUERIES)} queries...")
    kg_builder.build_knowledge_graph(QUERIES, batch_size=batch_size)
    
    kg_builder.save_knowledge_graph(output_dir)
    
    stats = kg_builder.get_graph_statistics()
    logger.info("Knowledge Graph Statistics:")
    for core_entity, data in stats["core_entities"].items():
        logger.info(f"Core entity '{core_entity}': {data['nodes']} nodes, {data['edges']} edges, {data['poison_edges']} poisoned edges")
    
    elapsed_time = time.time() - start_time
    logger.info(f"Knowledge graph construction completed, time taken: {elapsed_time:.2f} seconds")
    logger.info("=== Knowledge Graph Construction Ended ===")
    
    return os.path.join(output_dir, "graph_data.json")

def run_poison_text_generator(graph_data_path, output_dir, logger):
    logger.info("=== Poisoned Text Generation Started ===")
    
    start_time = time.time()
    
    output_path = os.path.join(output_dir, "poison_texts.json")
    
    prompt_template_path = os.path.join("poison_generator", "prompt_poison_text_generator.py")
    
    generator = PoisonTextGenerator(
        api_key=API_KEY,
        prompt_template_path=prompt_template_path
    )
    
    generator.run(graph_data_path, output_path)
    
    elapsed_time = time.time() - start_time
    logger.info(f"Poisoned text generation completed, time taken: {elapsed_time:.2f} seconds")
    logger.info("=== Poisoned Text Generation Ended ===")
    
    return output_path

def run_poison_text_enhancer(graph_data_path, output_dir, logger):
    logger.info("=== Poisoned Text Enhancement Started ===")
    
    start_time = time.time()
    
    output_path = os.path.join(output_dir, "enhanced_poison_texts.json")
    
    enhancer = PoisonTextEnhancer(api_key=API_KEY)
    
    enhancer.run(graph_data_path, output_path)
    
    elapsed_time = time.time() - start_time
    logger.info(f"Poisoned text enhancement completed, time taken: {elapsed_time:.2f} seconds")
    logger.info("=== Poisoned Text Enhancement Ended ===")
    
    return output_path

def run_poison_text_merger(poison_texts_path, enhanced_texts_path, output_dir, logger):
    logger.info("=== Poisoned Text Merging Started ===")
    
    start_time = time.time()
    
    json_output_path = os.path.join(output_dir, "merged_poison_texts.json")
    txt_output_path = os.path.join(output_dir, "merged_poison_texts.txt")
    
    merger = PoisonTextMerger()
    
    merger.run(
        poison_texts_path=poison_texts_path, 
        enhanced_texts_path=enhanced_texts_path,
        json_output_path=json_output_path,
        txt_output_path=txt_output_path
    )
    
    elapsed_time = time.time() - start_time
    logger.info(f"Poisoned text merging completed, time taken: {elapsed_time:.2f} seconds")
    logger.info(f"JSON output: {json_output_path}")
    logger.info(f"TXT output: {txt_output_path}")
    logger.info("=== Poisoned Text Merging Ended ===")
    
    return json_output_path, txt_output_path


def main():
    args = parse_arguments()
    
    os.makedirs(args.output_dir, exist_ok=True)
    
    logger = setup_logging()
    logger.info("Starting Poisoned Knowledge Graph Generation Tool")
    logger.info(f"Output directory: {args.output_dir}")
    logger.info(f"Batch size: {args.batch_size}")
    
    graph_data_path = os.path.join(args.output_dir, "graph_data.json")
    poison_texts_path = os.path.join(args.output_dir, "poison_texts.json")
    enhanced_texts_path = os.path.join(args.output_dir, "enhanced_poison_texts.json")
    
    if args.run_all or args.run_graph:
        graph_data_path = run_knowledge_graph_builder(args.output_dir, args.batch_size, logger)
    
    if args.run_all or args.run_generator:
        if not os.path.exists(graph_data_path):
            logger.error(f"Knowledge graph file does not exist: {graph_data_path}")
            logger.error("Please run the knowledge graph construction step first")
            return
        poison_texts_path = run_poison_text_generator(graph_data_path, args.output_dir, logger)
    
    if args.run_all or args.run_enhancer:
        if not os.path.exists(graph_data_path):
            logger.error(f"Knowledge graph file does not exist: {graph_data_path}")
            logger.error("Please run the knowledge graph construction step first")
            return
        enhanced_texts_path = run_poison_text_enhancer(graph_data_path, args.output_dir, logger)
    
    if args.run_all or args.run_merger:
        if not os.path.exists(poison_texts_path):
            logger.error(f"Poisoned text file does not exist: {poison_texts_path}")
            logger.error("Please run the poisoned text generation step first")
            return
        if not os.path.exists(enhanced_texts_path):
            logger.error(f"Enhanced poisoned text file does not exist: {enhanced_texts_path}")
            logger.error("Please run the poisoned text enhancement step first")
            return
        run_poison_text_merger(poison_texts_path, enhanced_texts_path, args.output_dir, logger)
    
    logger.info("All processing completed!")

if __name__ == "__main__":
    main()