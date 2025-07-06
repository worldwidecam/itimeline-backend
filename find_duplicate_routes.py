import os
import re

def find_routes_in_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Look for route definitions
    app_routes = re.findall(r'@app\.route\([\'"]([^\'"]+)[\'"]', content)
    blueprint_routes = re.findall(r'@\w+_bp\.route\([\'"]([^\'"]+)[\'"]', content)
    
    # Look for function definitions
    functions = re.findall(r'def\s+(\w+)\s*\(', content)
    
    return {
        'file': file_path,
        'app_routes': app_routes,
        'blueprint_routes': blueprint_routes,
        'functions': functions
    }

def find_all_routes(directory):
    results = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                try:
                    result = find_routes_in_file(file_path)
                    if result['app_routes'] or result['blueprint_routes']:
                        results.append(result)
                except Exception as e:
                    print(f"Error processing {file_path}: {e}")
    return results

if __name__ == '__main__':
    directory = '.'  # Current directory
    results = find_all_routes(directory)
    
    print("=== Route Definitions ===")
    for result in results:
        print(f"\nFile: {result['file']}")
        if result['app_routes']:
            print("  App Routes:")
            for route in result['app_routes']:
                print(f"    {route}")
        if result['blueprint_routes']:
            print("  Blueprint Routes:")
            for route in result['blueprint_routes']:
                print(f"    {route}")
    
    # Look for functions with "cors" in the name
    print("\n=== Functions with 'cors' in name ===")
    for result in results:
        cors_functions = [f for f in result['functions'] if 'cors' in f.lower()]
        if cors_functions:
            print(f"\nFile: {result['file']}")
            for func in cors_functions:
                print(f"  {func}")
