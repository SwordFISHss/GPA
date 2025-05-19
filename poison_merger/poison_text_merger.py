import json
import os
import logging
from typing import Dict, Any, Optional, Tuple

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/poison_merger.log", mode='a'),
    ]
)
logger = logging.getLogger(__name__)

class PoisonTextMerger:
    def __init__(self):
        pass
    
    def load_json_file(self, file_path: str) -> Optional[Dict[str, Any]]:
        try:
            if not os.path.exists(file_path):
                logger.error(f"File does not exist: {file_path}")
                return None
                
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            logger.info(f"Successfully loaded file: {file_path}")
            return data
        except Exception as e:
            logger.error(f"Failed to load file {file_path}: {e}")
            return None
    
    def merge_poison_texts(self, poison_texts: Dict[str, Any], enhanced_texts: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
        merged_json = {}
        merged_txt = ""
        
        all_entities = set(poison_texts.keys()) | set(enhanced_texts.keys())
        logger.info(f"Merging process will handle {len(all_entities)} core entities")
        
        for entity in all_entities:
            original_text = ""
            enhanced_text = ""
            
            if entity in poison_texts:
                poison_data = poison_texts[entity]
                original_text = poison_data.get("poison_text", "")
            
            if entity in enhanced_texts:
                enhanced_data = enhanced_texts[entity]
                enhanced_text = enhanced_data.get("aggregated_text", "")
            
            final_text = ""
            if original_text and enhanced_text:
                final_text = f"{original_text}\n\n{enhanced_text}"
            elif original_text:
                final_text = original_text
            elif enhanced_text:
                final_text = enhanced_text
            
            if final_text:
                merged_json[entity] = {
                    "theme": entity,
                    "final_poison_text": final_text
                }
                
                merged_txt += f"Theme: {entity}\n"
                merged_txt += f"{'='*50}\n"
                merged_txt += f"{final_text}\n\n"
                merged_txt += f"{'-'*50}\n\n"
                
                logger.info(f"Successfully generated merged poison text for theme '{entity}'")
            else:
                logger.warning(f"Theme '{entity}' has no available poison text")
        
        return merged_json, merged_txt
    
    def save_merged_result(self, merged_json: Dict[str, Any], merged_txt: str, 
                          json_output_path: str, txt_output_path: str) -> None:
        try:
            os.makedirs(os.path.dirname(json_output_path), exist_ok=True)
            
            with open(json_output_path, 'w', encoding='utf-8') as f:
                json.dump(merged_json, f, ensure_ascii=False, indent=2)
            logger.info(f"Successfully saved JSON format merged poison text to: {json_output_path}")
            
            with open(txt_output_path, 'w', encoding='utf-8') as f:
                f.write(merged_txt)
            logger.info(f"Successfully saved TXT format merged poison text to: {txt_output_path}")
            
        except Exception as e:
            logger.error(f"Failed to save merged poison text: {e}")
    
    def run(self, poison_texts_path: str, enhanced_texts_path: str, 
            json_output_path: str = None, txt_output_path: str = None) -> None:
        if json_output_path is None:
            output_dir = os.path.dirname(poison_texts_path)
            json_output_path = os.path.join(output_dir, "merged_poison_texts.json")
        
        if txt_output_path is None:
            output_dir = os.path.dirname(poison_texts_path)
            txt_output_path = os.path.join(output_dir, "merged_poison_texts.txt")
        
        poison_texts = self.load_json_file(poison_texts_path)
        if not poison_texts:
            logger.error("Failed to load poison texts, merging process aborted")
            return
        
        enhanced_texts = self.load_json_file(enhanced_texts_path)
        if not enhanced_texts:
            logger.error("Failed to load enhanced poison texts, merging process aborted")
            return
        
        merged_json, merged_txt = self.merge_poison_texts(poison_texts, enhanced_texts)
        
        self.save_merged_result(merged_json, merged_txt, json_output_path, txt_output_path)
        
        total_entities = len(merged_json)
        logger.info(f"Merging completed! Generated merged poison text for {total_entities} themes")
        logger.info(f"JSON output: {json_output_path}")
        logger.info(f"TXT output: {txt_output_path}")