# AI-Powered Marketing Data Chatbot

An AI-powered data analysis tool that translates natural language business questions into optimized SQL queries. Built with **GPT-4o-mini**, **DuckDB**, and **Pydantic V2**, this bot specializes in analyzing marketing datasets with high precision and conversational context.

## 🌟 Key Features

- **Natural Language to SQL (Text-to-SQL)**: Use LLM to transform ambiguous business questions into precise parameterized queries.
- **Strict Schema Compliance**: Implements OpenAI's **Strict Mode** by recursively processing JSON Schemas to ensure 100% reliable LLM outputs without "hallucinated" fields.
- **Conversational State (Patching)**: Supports multi-turn conversations. You can ask a follow-up question (e.g., "Now only for Product 2") and the bot will intelligently "patch" the previous query state.
- **Robust Error Handling**: Specialized detection for `NaN` results and empty datasets, providing user-friendly advice instead of cryptic database errors.

## 🛠️ Tech Stack

- **Core Engine**: Python 3.9+
- **LLM**: OpenAI GPT-4o-mini
- **Database**: DuckDB (In-memory analytical processing)
- **Data Manipulation**: Pandas
- **Validation**: Pydantic V2 (Type safety & Strict JSON Schema)
- **Environment**: Python-dotenv

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.9 or higher
- An OpenAI API Key

### 2. Installation
Clone the repository:
```bash
git clone [https://github.com/ZhnegW/marketing-data-chatbot.git]
cd marketing-data-chatbot
```

Install dependencies:
```bash
pip install -r requirements.txt
```

### 3. Configuration
Create a .env file in the root directory:
```
OPENAI_API_KEY=your_actual_api_key_here
```

### 4. Run the Bot
```bash
python bot_cli.py
```

## 📊 Example Queries
- **Global Query**: “Show me total revenue for all years”
- **Multi-dimensional Analysis**: “Which media categories had the highest profit in Q2 2023?”
- **Contextual Follow-up**: “Now only for Product = 2”
- **Trend Analysis**: “Revenue and cost trend by month”

## 📂 Project Structure
- `bot_cli.py`: The interactive command-line interface.
- `llm_parser.py`: Handles LLM communication and recursive JSON Schema strictness.
- `executor.py`: The SQL engine. Translates QuerySpec into DuckDB SQL.
- `schema.py`: Pydantic models defining the "Source of Truth" for data structures.
- `state.py`: Manages the application state and applies "patches" for multi-turn logic.
