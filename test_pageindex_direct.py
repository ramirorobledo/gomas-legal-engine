import os
import sys
import logging
import indexer

# Setup logging to console
logging.basicConfig(level=logging.INFO)

def test_direct_indexing():
    print("Testing direct PageIndex integration...")
    
    # Create dummy MD
    dummy_md = "test_doc.md"
    with open(dummy_md, "w", encoding="utf-8") as f:
        f.write("# Título Legal\n\n## Sección 1\nContenido de prueba para el índice.\n\n## Sección 2\nMás contenido legal relevante.")
        
    output_dir = "indices_test"
    os.makedirs(output_dir, exist_ok=True)
    
    try:
        print("Running create_index...")
        output_path = indexer.create_index(dummy_md, "test_999", output_dir)
        print(f"Index created at: {output_path}")
        
        if os.path.exists(output_path):
            print("✅ SUCCESS: Output file exists.")
            with open(output_path, "r", encoding="utf-8") as f:
                print("Content preview:", f.read()[:200])
        else:
            print("❌ FAILURE: Output file not found.")
            
    except Exception as e:
        print(f"❌ EXCEPTION: {e}")
    finally:
        # Cleanup
        if os.path.exists(dummy_md):
            os.remove(dummy_md)
        # if os.path.exists(output_dir):
        #    shutil.rmtree(output_dir)

if __name__ == "__main__":
    test_direct_indexing()
