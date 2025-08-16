from parser import OpenAPIParser
from scorecard import run_scorecard

# Load spec with your parser
parser = OpenAPIParser("simple-api.yaml")
spec = parser.load_spec()
parser.validate()

# Run scorecard
results = run_scorecard(spec)

print("📊 Scorecard Results:")
print(results)
