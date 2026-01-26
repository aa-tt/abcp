"""
Custom Database with Query Language
Demonstrates: Classes, magic methods, pickle/JSON serialization, indexing,
searching algorithms, decorators, context managers
"""

import pickle
import json
from typing import Dict, List, Any, Optional, Callable
from functools import wraps
from contextlib import contextmanager
from datetime import datetime
import re
from pathlib import Path


# Decorators
def transaction(func: Callable) -> Callable:
    """Decorator for database transactions with rollback support."""
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        # Create backup before transaction
        backup = self._create_backup()
        try:
            result = func(self, *args, **kwargs)
            return result
        except Exception as e:
            # Rollback on error
            self._restore_backup(backup)
            raise Exception(f"Transaction failed, rolled back: {e}")
    return wrapper


def validate_table_exists(func: Callable) -> Callable:
    """Decorator to validate table exists."""
    @wraps(func)
    def wrapper(self, table_name, *args, **kwargs):
        if table_name not in self.tables:
            raise ValueError(f"Table '{table_name}' does not exist")
        return func(self, table_name, *args, **kwargs)
    return wrapper


# Context Manager
@contextmanager
def database_connection(db_path: str, auto_save: bool = True):
    """Context manager for database connections."""
    print(f"📂 Opening database: {db_path}")
    db = Database(db_path)
    db.load()
    try:
        yield db
    finally:
        if auto_save:
            db.save()
            print(f"💾 Database saved and closed")
        else:
            print(f"📂 Database closed without saving")


class Index:
    """Index for fast searching on a column."""
    
    def __init__(self, column_name: str):
        self.column_name = column_name
        self.index: Dict[Any, List[int]] = {}  # value -> list of row indices
    
    def build(self, rows: List[Dict]):
        """Build index from rows."""
        self.index.clear()
        for i, row in enumerate(rows):
            value = row.get(self.column_name)
            if value is not None:
                if value not in self.index:
                    self.index[value] = []
                self.index[value].append(i)
    
    def search(self, value: Any) -> List[int]:
        """Search for value in index."""
        return self.index.get(value, [])
    
    def __repr__(self):
        return f"Index(column={self.column_name}, entries={len(self.index)})"


class Table:
    """Database table with magic methods."""
    
    def __init__(self, name: str, columns: List[str]):
        self.name = name
        self.columns = columns
        self.rows: List[Dict] = []
        self.indexes: Dict[str, Index] = {}
        self.auto_increment_id = 1
    
    # Magic Methods
    def __len__(self) -> int:
        """Return number of rows."""
        return len(self.rows)
    
    def __getitem__(self, key) -> Dict:
        """Get row by index or slice."""
        return self.rows[key]
    
    def __iter__(self):
        """Iterate over rows."""
        return iter(self.rows)
    
    def __contains__(self, row: Dict) -> bool:
        """Check if row exists in table."""
        return row in self.rows
    
    def __repr__(self):
        return f"Table(name='{self.name}', columns={self.columns}, rows={len(self.rows)})"
    
    def __str__(self):
        """Pretty print table."""
        if not self.rows:
            return f"Table '{self.name}' (empty)"
        
        # Calculate column widths
        widths = {col: len(col) for col in self.columns}
        for row in self.rows:
            for col in self.columns:
                widths[col] = max(widths[col], len(str(row.get(col, ''))))
        
        # Build table string
        header = " | ".join(col.ljust(widths[col]) for col in self.columns)
        separator = "-+-".join("-" * widths[col] for col in self.columns)
        
        lines = [f"Table: {self.name}", separator, header, separator]
        
        for row in self.rows[:20]:  # Limit to 20 rows for display
            line = " | ".join(str(row.get(col, '')).ljust(widths[col]) for col in self.columns)
            lines.append(line)
        
        if len(self.rows) > 20:
            lines.append(f"... and {len(self.rows) - 20} more rows")
        
        lines.append(separator)
        return "\n".join(lines)
    
    def insert(self, row: Dict) -> int:
        """Insert a row into the table."""
        # Validate columns
        for col in self.columns:
            if col not in row and col != 'id':
                row[col] = None
        
        # Add auto-increment ID if not provided
        if 'id' in self.columns and 'id' not in row:
            row['id'] = self.auto_increment_id
            self.auto_increment_id += 1
        
        # Insert row
        self.rows.append(row)
        row_index = len(self.rows) - 1
        
        # Update indexes
        for index in self.indexes.values():
            if index.column_name in row:
                value = row[index.column_name]
                if value not in index.index:
                    index.index[value] = []
                index.index[value].append(row_index)
        
        return row_index
    
    def delete(self, condition: Callable[[Dict], bool]) -> int:
        """Delete rows matching condition."""
        initial_count = len(self.rows)
        self.rows = [row for row in self.rows if not condition(row)]
        deleted = initial_count - len(self.rows)
        
        # Rebuild indexes after deletion
        for index in self.indexes.values():
            index.build(self.rows)
        
        return deleted
    
    def update(self, condition: Callable[[Dict], bool], updates: Dict) -> int:
        """Update rows matching condition."""
        updated_count = 0
        for row in self.rows:
            if condition(row):
                row.update(updates)
                updated_count += 1
        
        # Rebuild indexes if updated columns are indexed
        for col in updates.keys():
            if col in self.indexes:
                self.indexes[col].build(self.rows)
        
        return updated_count
    
    def select(self, condition: Optional[Callable[[Dict], bool]] = None,
               columns: Optional[List[str]] = None) -> List[Dict]:
        """Select rows matching condition."""
        # Filter rows
        if condition:
            filtered_rows = [row for row in self.rows if condition(row)]
        else:
            filtered_rows = self.rows
        
        # Project columns
        if columns:
            result = []
            for row in filtered_rows:
                projected_row = {col: row.get(col) for col in columns if col in self.columns}
                result.append(projected_row)
            return result
        
        return filtered_rows.copy()
    
    def create_index(self, column_name: str):
        """Create an index on a column."""
        if column_name not in self.columns:
            raise ValueError(f"Column '{column_name}' does not exist")
        
        if column_name in self.indexes:
            print(f"Index on '{column_name}' already exists")
            return
        
        index = Index(column_name)
        index.build(self.rows)
        self.indexes[column_name] = index
        print(f"✓ Created index on '{column_name}'")
    
    def search_indexed(self, column_name: str, value: Any) -> List[Dict]:
        """Search using index if available."""
        if column_name in self.indexes:
            indices = self.indexes[column_name].search(value)
            return [self.rows[i] for i in indices]
        else:
            # Fall back to linear search
            return [row for row in self.rows if row.get(column_name) == value]


class QueryParser:
    """Parse and execute custom query language."""
    
    # Query patterns
    INSERT_PATTERN = re.compile(
        r'INSERT INTO (\w+) \((.*?)\) VALUES \((.*?)\)',
        re.IGNORECASE
    )
    
    SELECT_PATTERN = re.compile(
        r'SELECT (.*?) FROM (\w+)(?: WHERE (.+?))?(?:$|;)',
        re.IGNORECASE
    )
    
    UPDATE_PATTERN = re.compile(
        r'UPDATE (\w+) SET (.+?)(?: WHERE (.+?))?(?:$|;)',
        re.IGNORECASE
    )
    
    DELETE_PATTERN = re.compile(
        r'DELETE FROM (\w+)(?: WHERE (.+?))?(?:$|;)',
        re.IGNORECASE
    )
    
    CREATE_PATTERN = re.compile(
        r'CREATE TABLE (\w+) \((.*?)\)',
        re.IGNORECASE
    )
    
    @staticmethod
    def parse_value(value_str: str) -> Any:
        """Parse value from string."""
        value_str = value_str.strip()
        
        # Remove quotes for strings
        if (value_str.startswith("'") and value_str.endswith("'")) or \
           (value_str.startswith('"') and value_str.endswith('"')):
            return value_str[1:-1]
        
        # Parse numbers
        try:
            if '.' in value_str:
                return float(value_str)
            return int(value_str)
        except ValueError:
            return value_str
    
    @staticmethod
    def parse_condition(condition_str: str) -> Callable[[Dict], bool]:
        """Parse WHERE condition into a function."""
        # Simple condition parser: column operator value
        # Supports: =, !=, >, <, >=, <=
        
        operators = {
            '=': lambda a, b: a == b,
            '!=': lambda a, b: a != b,
            '>': lambda a, b: a > b,
            '<': lambda a, b: a < b,
            '>=': lambda a, b: a >= b,
            '<=': lambda a, b: a <= b,
        }
        
        # Find operator
        for op_str, op_func in operators.items():
            if op_str in condition_str:
                parts = condition_str.split(op_str, 1)
                if len(parts) == 2:
                    column = parts[0].strip()
                    value = QueryParser.parse_value(parts[1])
                    
                    return lambda row, c=column, v=value, f=op_func: f(row.get(c), v)
        
        # Default: always true
        return lambda row: True
    
    def parse_insert(self, query: str, db: 'Database'):
        """Parse and execute INSERT query."""
        match = self.INSERT_PATTERN.match(query)
        if not match:
            raise ValueError("Invalid INSERT syntax")
        
        table_name = match.group(1)
        columns = [col.strip() for col in match.group(2).split(',')]
        values = [self.parse_value(val) for val in match.group(3).split(',')]
        
        if len(columns) != len(values):
            raise ValueError("Column count doesn't match value count")
        
        row = dict(zip(columns, values))
        return db.insert(table_name, row)
    
    def parse_select(self, query: str, db: 'Database'):
        """Parse and execute SELECT query."""
        match = self.SELECT_PATTERN.match(query)
        if not match:
            raise ValueError("Invalid SELECT syntax")
        
        columns_str = match.group(1).strip()
        table_name = match.group(2)
        where_clause = match.group(3)
        
        # Parse columns
        if columns_str == '*':
            columns = None
        else:
            columns = [col.strip() for col in columns_str.split(',')]
        
        # Parse condition
        condition = None
        if where_clause:
            condition = self.parse_condition(where_clause)
        
        return db.select(table_name, condition, columns)
    
    def parse_update(self, query: str, db: 'Database'):
        """Parse and execute UPDATE query."""
        match = self.UPDATE_PATTERN.match(query)
        if not match:
            raise ValueError("Invalid UPDATE syntax")
        
        table_name = match.group(1)
        set_clause = match.group(2)
        where_clause = match.group(3)
        
        # Parse SET clause
        updates = {}
        for assignment in set_clause.split(','):
            col, val = assignment.split('=', 1)
            updates[col.strip()] = self.parse_value(val)
        
        # Parse condition
        condition = None
        if where_clause:
            condition = self.parse_condition(where_clause)
        
        return db.update(table_name, condition, updates)
    
    def parse_delete(self, query: str, db: 'Database'):
        """Parse and execute DELETE query."""
        match = self.DELETE_PATTERN.match(query)
        if not match:
            raise ValueError("Invalid DELETE syntax")
        
        table_name = match.group(1)
        where_clause = match.group(2)
        
        # Parse condition
        condition = None
        if where_clause:
            condition = self.parse_condition(where_clause)
        else:
            # Require WHERE clause for DELETE to prevent accidents
            raise ValueError("DELETE requires WHERE clause (use WHERE 1=1 to delete all)")
        
        return db.delete(table_name, condition)
    
    def parse_create(self, query: str, db: 'Database'):
        """Parse and execute CREATE TABLE query."""
        match = self.CREATE_PATTERN.match(query)
        if not match:
            raise ValueError("Invalid CREATE TABLE syntax")
        
        table_name = match.group(1)
        columns_str = match.group(2)
        
        # Parse columns
        columns = [col.strip().split()[0] for col in columns_str.split(',')]
        
        return db.create_table(table_name, columns)
    
    def execute(self, query: str, db: 'Database'):
        """Execute a query."""
        query = query.strip()
        
        if query.upper().startswith('INSERT'):
            return self.parse_insert(query, db)
        elif query.upper().startswith('SELECT'):
            return self.parse_select(query, db)
        elif query.upper().startswith('UPDATE'):
            return self.parse_update(query, db)
        elif query.upper().startswith('DELETE'):
            return self.parse_delete(query, db)
        elif query.upper().startswith('CREATE'):
            return self.parse_create(query, db)
        else:
            raise ValueError(f"Unknown query type: {query[:20]}")


class Database:
    """Custom database with multiple tables."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.tables: Dict[str, Table] = {}
        self.query_parser = QueryParser()
    
    def create_table(self, table_name: str, columns: List[str]) -> Table:
        """Create a new table."""
        if table_name in self.tables:
            raise ValueError(f"Table '{table_name}' already exists")
        
        table = Table(table_name, columns)
        self.tables[table_name] = table
        print(f"✓ Created table '{table_name}' with columns: {columns}")
        return table
    
    @validate_table_exists
    def drop_table(self, table_name: str):
        """Drop a table."""
        del self.tables[table_name]
        print(f"✓ Dropped table '{table_name}'")
    
    @validate_table_exists
    def insert(self, table_name: str, row: Dict) -> int:
        """Insert row into table."""
        return self.tables[table_name].insert(row)
    
    @validate_table_exists
    def select(self, table_name: str, 
               condition: Optional[Callable[[Dict], bool]] = None,
               columns: Optional[List[str]] = None) -> List[Dict]:
        """Select rows from table."""
        return self.tables[table_name].select(condition, columns)
    
    @validate_table_exists
    def update(self, table_name: str,
               condition: Optional[Callable[[Dict], bool]],
               updates: Dict) -> int:
        """Update rows in table."""
        if condition is None:
            condition = lambda row: True
        return self.tables[table_name].update(condition, updates)
    
    @validate_table_exists
    def delete(self, table_name: str,
               condition: Callable[[Dict], bool]) -> int:
        """Delete rows from table."""
        return self.tables[table_name].delete(condition)
    
    @transaction
    def execute_query(self, query: str):
        """Execute a SQL-like query."""
        return self.query_parser.execute(query, self)
    
    def save(self, format: str = 'pickle'):
        """Save database to file using pickle or JSON."""
        try:
            if format == 'pickle':
                self._save_pickle()
            elif format == 'json':
                self._save_json()
            else:
                raise ValueError(f"Unknown format: {format}")
        except Exception as e:
            print(f"Error saving database: {e}")
            raise
    
    def _save_pickle(self):
        """Save using pickle (binary, preserves types)."""
        with open(self.db_path + '.db', 'wb') as f:
            pickle.dump(self.tables, f)
        print(f"✓ Database saved (pickle): {self.db_path}.db")
    
    def _save_json(self):
        """Save using JSON (text, human-readable)."""
        data = {
            'tables': {}
        }
        
        for table_name, table in self.tables.items():
            data['tables'][table_name] = {
                'columns': table.columns,
                'rows': table.rows,
                'auto_increment_id': table.auto_increment_id
            }
        
        with open(self.db_path + '.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"✓ Database saved (JSON): {self.db_path}.json")
    
    def load(self, format: str = 'pickle'):
        """Load database from file."""
        try:
            if format == 'pickle':
                self._load_pickle()
            elif format == 'json':
                self._load_json()
            else:
                raise ValueError(f"Unknown format: {format}")
        except FileNotFoundError:
            print(f"Database file not found, starting fresh")
        except Exception as e:
            print(f"Error loading database: {e}")
            raise
    
    def _load_pickle(self):
        """Load using pickle."""
        path = Path(self.db_path + '.db')
        if path.exists():
            with open(path, 'rb') as f:
                self.tables = pickle.load(f)
            print(f"✓ Database loaded (pickle): {len(self.tables)} tables")
    
    def _load_json(self):
        """Load using JSON."""
        path = Path(self.db_path + '.json')
        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.tables = {}
            for table_name, table_data in data['tables'].items():
                table = Table(table_name, table_data['columns'])
                table.rows = table_data['rows']
                table.auto_increment_id = table_data['auto_increment_id']
                self.tables[table_name] = table
            
            print(f"✓ Database loaded (JSON): {len(self.tables)} tables")
    
    def _create_backup(self) -> Dict:
        """Create backup of current state (for transactions)."""
        backup = {}
        for table_name, table in self.tables.items():
            backup[table_name] = {
                'columns': table.columns.copy(),
                'rows': [row.copy() for row in table.rows],
                'auto_increment_id': table.auto_increment_id
            }
        return backup
    
    def _restore_backup(self, backup: Dict):
        """Restore from backup (for transaction rollback)."""
        self.tables = {}
        for table_name, table_data in backup.items():
            table = Table(table_name, table_data['columns'])
            table.rows = table_data['rows']
            table.auto_increment_id = table_data['auto_increment_id']
            self.tables[table_name] = table
    
    def list_tables(self):
        """List all tables."""
        if not self.tables:
            print("No tables in database")
            return
        
        print(f"\nTables in database ({len(self.tables)}):")
        for table_name, table in self.tables.items():
            print(f"  - {table_name}: {len(table)} rows, columns: {table.columns}")
    
    def __repr__(self):
        return f"Database(path='{self.db_path}', tables={len(self.tables)})"


def demo():
    """Demonstrate database features."""
    print("="*70)
    print("CUSTOM DATABASE DEMO")
    print("="*70)
    
    # Using context manager
    with database_connection("demo_db", auto_save=True) as db:
        
        # Create tables
        print("\n--- Creating Tables ---")
        db.create_table('users', ['id', 'name', 'email', 'age'])
        db.create_table('products', ['id', 'name', 'price', 'stock'])
        
        # Insert data using method calls
        print("\n--- Inserting Data (Method Calls) ---")
        db.insert('users', {'name': 'Alice', 'email': 'alice@example.com', 'age': 28})
        db.insert('users', {'name': 'Bob', 'email': 'bob@example.com', 'age': 35})
        db.insert('users', {'name': 'Charlie', 'email': 'charlie@example.com', 'age': 22})
        
        db.insert('products', {'name': 'Laptop', 'price': 999.99, 'stock': 10})
        db.insert('products', {'name': 'Mouse', 'price': 29.99, 'stock': 50})
        db.insert('products', {'name': 'Keyboard', 'price': 79.99, 'stock': 30})
        
        # Insert using SQL-like queries
        print("\n--- Inserting Data (SQL Queries) ---")
        db.execute_query("INSERT INTO users (name, email, age) VALUES ('David', 'david@example.com', 42)")
        db.execute_query("INSERT INTO products (name, price, stock) VALUES ('Monitor', 299.99, 15)")
        
        # Create indexes
        print("\n--- Creating Indexes ---")
        db.tables['users'].create_index('name')
        db.tables['products'].create_index('price')
        
        # Select all
        print("\n--- SELECT * FROM users ---")
        users = db.execute_query("SELECT * FROM users")
        for user in users:
            print(f"  {user}")
        
        # Select with WHERE
        print("\n--- SELECT * FROM users WHERE age > 25 ---")
        adults = db.execute_query("SELECT * FROM users WHERE age>25")
        for user in adults:
            print(f"  {user}")
        
        # Select specific columns
        print("\n--- SELECT name, email FROM users ---")
        names = db.execute_query("SELECT name, email FROM users")
        for user in names:
            print(f"  {user}")
        
        # Update
        print("\n--- UPDATE products SET price = 899.99 WHERE name = 'Laptop' ---")
        updated = db.execute_query("UPDATE products SET price=899.99 WHERE name='Laptop'")
        print(f"  Updated {updated} rows")
        
        # Using magic methods
        print("\n--- Magic Methods Demo ---")
        users_table = db.tables['users']
        print(f"Table length: {len(users_table)}")  # __len__
        print(f"First user: {users_table[0]}")  # __getitem__
        print(f"\nIterating over users:")  # __iter__
        for user in users_table:
            print(f"  - {user['name']}")
        
        # Display tables
        print("\n--- Table Display (str) ---")
        print(db.tables['products'])
        
        # Delete
        print("\n--- DELETE FROM users WHERE age < 25 ---")
        deleted = db.execute_query("DELETE FROM users WHERE age<25")
        print(f"  Deleted {deleted} rows")
        
        # Final state
        print("\n--- Final State ---")
        db.list_tables()
        
        print("\n--- All Users ---")
        print(db.tables['users'])


def interactive_mode():
    """Interactive database shell."""
    print("="*70)
    print("CUSTOM DATABASE - INTERACTIVE MODE")
    print("="*70)
    print("\nCommands:")
    print("  CREATE TABLE <name> (<columns>)")
    print("  INSERT INTO <table> (<columns>) VALUES (<values>)")
    print("  SELECT <columns> FROM <table> [WHERE <condition>]")
    print("  UPDATE <table> SET <column>=<value> [WHERE <condition>]")
    print("  DELETE FROM <table> WHERE <condition>")
    print("  SHOW TABLES")
    print("  DESCRIBE <table>")
    print("  SAVE [pickle|json]")
    print("  EXIT")
    print("="*70)
    
    db_name = input("\nDatabase name (default: 'mydb'): ").strip() or 'mydb'
    db = Database(db_name)
    
    # Try to load existing database
    format_choice = input("Load format? (pickle/json, Enter to skip): ").strip().lower()
    if format_choice in ['pickle', 'json']:
        db.load(format_choice)
    
    while True:
        try:
            query = input("\ndb> ").strip()
            
            if not query:
                continue
            
            if query.upper() == 'EXIT':
                save = input("Save before exit? (y/n): ").lower()
                if save == 'y':
                    fmt = input("Format (pickle/json): ").strip().lower() or 'pickle'
                    db.save(fmt)
                print("Goodbye!")
                break
            
            elif query.upper() == 'SHOW TABLES':
                db.list_tables()
            
            elif query.upper().startswith('DESCRIBE'):
                table_name = query.split()[1]
                if table_name in db.tables:
                    print(db.tables[table_name])
                else:
                    print(f"Table '{table_name}' not found")
            
            elif query.upper().startswith('SAVE'):
                parts = query.split()
                fmt = parts[1] if len(parts) > 1 else 'pickle'
                db.save(fmt)
            
            else:
                result = db.execute_query(query)
                if isinstance(result, list):
                    if result:
                        print(f"\nResult ({len(result)} rows):")
                        for i, row in enumerate(result[:20], 1):
                            print(f"  {i}. {row}")
                        if len(result) > 20:
                            print(f"  ... and {len(result) - 20} more rows")
                    else:
                        print("No results")
                elif isinstance(result, int):
                    print(f"✓ Affected rows: {result}")
                else:
                    print(f"✓ Success")
        
        except KeyboardInterrupt:
            print("\nUse EXIT to quit")
        except Exception as e:
            print(f"✗ Error: {e}")


def main():
    """Main application."""
    print("\n1. Run Demo")
    print("2. Interactive Mode")
    choice = input("\nChoice (1 or 2): ").strip()
    
    if choice == '1':
        demo()
    else:
        interactive_mode()


if __name__ == "__main__":
    main()

"""
Key Features:

* Classes: Database, Table, Index, QueryParser with full OOP design
* Magic Methods: __len__, __getitem__, __iter__, __contains__, __str__, __repr__
* Pickle/JSON Serialization: Save and load database in both formats
* Indexing: Fast searching with B-tree-like indexes
* Query Language: SQL-like syntax (SELECT, INSERT, UPDATE, DELETE, CREATE TABLE)
* Decorators: @transaction for rollback, @validate_table_exists for validation
* Context Managers: @contextmanager for automatic database save/close

Demonstrates:

* Custom magic methods for Pythonic interfaces
* Pickle for binary serialization
* JSON for text-based serialization
* Index-based searching algorithms
* Regex-based query parsing
* Transaction management with backup/rollback
* Context manager for resource management
* Decorator pattern for validation and transactions

Query Language Syntax:

CREATE TABLE users (id, name, email, age)
INSERT INTO users (name, email, age) VALUES ('Alice', 'alice@example.com', 28)
SELECT * FROM users WHERE age > 25
UPDATE users SET age = 30 WHERE name = 'Alice'
DELETE FROM users WHERE age < 18

"""