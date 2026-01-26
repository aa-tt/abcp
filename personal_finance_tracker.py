"""
Personal Finance Tracker
Demonstrates: Classes, decorators, context managers, file I/O, datetime operations,
sorting/filtering, lambda functions, data validation
"""

import json
import csv
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Callable
from functools import wraps
from contextlib import contextmanager
from pathlib import Path
import statistics


# Decorators
def validate_amount(func: Callable) -> Callable:
    """Decorator to validate transaction amounts."""
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        amount = kwargs.get('amount') or (args[0] if args else None)
        if amount is not None and amount <= 0:
            raise ValueError("Amount must be positive")
        return func(self, *args, **kwargs)
    return wrapper


def log_transaction(func: Callable) -> Callable:
    """Decorator to log transaction operations."""
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        result = func(self, *args, **kwargs)
        if result:
            print(f"✓ Transaction {func.__name__}: ID {result.id if hasattr(result, 'id') else 'N/A'}")
        return result
    return wrapper


def validate_date(func: Callable) -> Callable:
    """Decorator to validate date inputs."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        date_str = kwargs.get('date')
        if date_str:
            try:
                datetime.fromisoformat(date_str)
            except ValueError:
                raise ValueError(f"Invalid date format: {date_str}. Use YYYY-MM-DD")
        return func(*args, **kwargs)
    return wrapper


# Context Managers
@contextmanager
def transaction_batch(tracker):
    """Context manager for batch transaction operations."""
    print("\n📝 Starting transaction batch...")
    tracker.start_batch()
    try:
        yield tracker
        print("✓ Committing batch...")
        tracker.commit_batch()
    except Exception as e:
        print(f"✗ Error in batch, rolling back: {e}")
        tracker.rollback_batch()
        raise
    finally:
        print("✓ Transaction batch completed")


class Transaction:
    """Represents a single financial transaction."""
    
    CATEGORIES = {
        'income': ['salary', 'freelance', 'investment', 'gift', 'other_income'],
        'expense': ['food', 'transport', 'utilities', 'entertainment', 'shopping', 
                   'healthcare', 'education', 'rent', 'other_expense']
    }
    
    def __init__(self, amount: float, category: str, description: str, 
                 transaction_type: str, date: Optional[str] = None):
        self.id = None
        self.amount = self._validate_amount(amount)
        self.category = self._validate_category(category, transaction_type)
        self.description = description.strip()
        self.transaction_type = self._validate_type(transaction_type)
        self.date = date if date else datetime.now().isoformat()
        self.created_at = datetime.now().isoformat()
    
    def _validate_amount(self, amount: float) -> float:
        """Validate transaction amount."""
        if not isinstance(amount, (int, float)) or amount <= 0:
            raise ValueError("Amount must be a positive number")
        return round(float(amount), 2)
    
    def _validate_type(self, transaction_type: str) -> str:
        """Validate transaction type."""
        transaction_type = transaction_type.lower()
        if transaction_type not in ['income', 'expense']:
            raise ValueError("Transaction type must be 'income' or 'expense'")
        return transaction_type
    
    def _validate_category(self, category: str, transaction_type: str) -> str:
        """Validate transaction category."""
        category = category.lower()
        valid_categories = self.CATEGORIES.get(transaction_type.lower(), [])
        if category not in valid_categories:
            raise ValueError(f"Invalid category. Use: {', '.join(valid_categories)}")
        return category
    
    def to_dict(self) -> Dict:
        """Convert transaction to dictionary."""
        return {
            'id': self.id,
            'amount': self.amount,
            'category': self.category,
            'description': self.description,
            'transaction_type': self.transaction_type,
            'date': self.date,
            'created_at': self.created_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Transaction':
        """Create transaction from dictionary."""
        transaction = cls(
            amount=data['amount'],
            category=data['category'],
            description=data['description'],
            transaction_type=data['transaction_type'],
            date=data.get('date')
        )
        transaction.id = data.get('id')
        transaction.created_at = data.get('created_at', transaction.created_at)
        return transaction
    
    def __str__(self) -> str:
        sign = '+' if self.transaction_type == 'income' else '-'
        return f"[{self.id}] {self.date[:10]} | {sign}${self.amount:.2f} | {self.category} | {self.description}"
    
    def __repr__(self) -> str:
        return f"Transaction(id={self.id}, type={self.transaction_type}, amount={self.amount})"


class Budget:
    """Represents a budget for a category."""
    
    def __init__(self, category: str, limit: float, period: str = 'monthly'):
        self.category = category.lower()
        self.limit = limit
        self.period = period  # daily, weekly, monthly, yearly
        self.created_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict:
        return {
            'category': self.category,
            'limit': self.limit,
            'period': self.period,
            'created_at': self.created_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Budget':
        budget = cls(data['category'], data['limit'], data.get('period', 'monthly'))
        budget.created_at = data.get('created_at', budget.created_at)
        return budget


class FinanceTracker:
    """Main finance tracker with file persistence and analysis."""
    
    def __init__(self, filename: str = "finance_data.json"):
        self.filename = filename
        self.transactions: List[Transaction] = []
        self.budgets: List[Budget] = []
        self.next_id = 1
        self._batch_mode = False
        self._batch_backup = None
        self.load()
    
    @log_transaction
    @validate_amount
    def add_transaction(self, amount: float, category: str, description: str,
                       transaction_type: str, date: Optional[str] = None) -> Transaction:
        """Add a new transaction."""
        transaction = Transaction(amount, category, description, transaction_type, date)
        transaction.id = self.next_id
        self.transactions.append(transaction)
        self.next_id += 1
        
        if not self._batch_mode:
            self.save()
        
        # Check budget warnings
        self._check_budget_warning(transaction)
        
        return transaction
    
    def _check_budget_warning(self, transaction: Transaction):
        """Check if transaction exceeds budget."""
        if transaction.transaction_type != 'expense':
            return
        
        for budget in self.budgets:
            if budget.category == transaction.category:
                spent = self.get_category_spending(
                    transaction.category,
                    period=budget.period
                )
                if spent > budget.limit:
                    print(f"\n⚠️  WARNING: Budget exceeded for {budget.category}!")
                    print(f"   Spent: ${spent:.2f} | Budget: ${budget.limit:.2f}")
                elif spent > budget.limit * 0.8:
                    print(f"\n⚠️  ALERT: {budget.category} at {(spent/budget.limit)*100:.1f}% of budget")
    
    def get_transaction(self, transaction_id: int) -> Optional[Transaction]:
        """Get transaction by ID."""
        for transaction in self.transactions:
            if transaction.id == transaction_id:
                return transaction
        return None
    
    def delete_transaction(self, transaction_id: int) -> bool:
        """Delete a transaction."""
        transaction = self.get_transaction(transaction_id)
        if transaction:
            self.transactions.remove(transaction)
            self.save()
            return True
        return False
    
    def add_budget(self, category: str, limit: float, period: str = 'monthly'):
        """Add or update a budget."""
        # Remove existing budget for category
        self.budgets = [b for b in self.budgets if b.category != category.lower()]
        
        budget = Budget(category, limit, period)
        self.budgets.append(budget)
        self.save()
        print(f"✓ Budget set: {category} - ${limit:.2f}/{period}")
    
    def get_balance(self) -> float:
        """Calculate current balance."""
        income = sum(t.amount for t in self.transactions if t.transaction_type == 'income')
        expenses = sum(t.amount for t in self.transactions if t.transaction_type == 'expense')
        return round(income - expenses, 2)
    
    def get_transactions_by_date_range(self, start_date: str, end_date: str) -> List[Transaction]:
        """Get transactions within date range using lambda for filtering."""
        start = datetime.fromisoformat(start_date)
        end = datetime.fromisoformat(end_date)
        
        # Using lambda function for filtering
        return list(filter(
            lambda t: start <= datetime.fromisoformat(t.date) <= end,
            self.transactions
        ))
    
    def get_transactions_by_category(self, category: str) -> List[Transaction]:
        """Get all transactions for a category."""
        return [t for t in self.transactions if t.category == category.lower()]
    
    def get_category_spending(self, category: str, period: str = 'monthly') -> float:
        """Get total spending for a category in a period."""
        now = datetime.now()
        
        # Calculate period start date
        if period == 'daily':
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == 'weekly':
            start_date = now - timedelta(days=now.weekday())
        elif period == 'monthly':
            start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        elif period == 'yearly':
            start_date = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            start_date = datetime.min
        
        transactions = self.get_transactions_by_date_range(
            start_date.isoformat(),
            now.isoformat()
        )
        
        return sum(
            t.amount for t in transactions
            if t.category == category.lower() and t.transaction_type == 'expense'
        )
    
    def get_summary(self, period: str = 'all') -> Dict:
        """Get financial summary with sorting and statistics."""
        if period != 'all':
            transactions = self._get_period_transactions(period)
        else:
            transactions = self.transactions
        
        if not transactions:
            return {'error': 'No transactions found'}
        
        # Calculate totals using lambda
        income_transactions = list(filter(lambda t: t.transaction_type == 'income', transactions))
        expense_transactions = list(filter(lambda t: t.transaction_type == 'expense', transactions))
        
        total_income = sum(t.amount for t in income_transactions)
        total_expenses = sum(t.amount for t in expense_transactions)
        
        # Category breakdown using dict comprehension
        income_by_category = {}
        expense_by_category = {}
        
        for t in income_transactions:
            income_by_category[t.category] = income_by_category.get(t.category, 0) + t.amount
        
        for t in expense_transactions:
            expense_by_category[t.category] = expense_by_category.get(t.category, 0) + t.amount
        
        # Sort categories by amount (using lambda for sorting)
        sorted_expenses = sorted(
            expense_by_category.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        # Calculate statistics
        expense_amounts = [t.amount for t in expense_transactions]
        
        summary = {
            'period': period,
            'total_income': round(total_income, 2),
            'total_expenses': round(total_expenses, 2),
            'net_savings': round(total_income - total_expenses, 2),
            'savings_rate': round((total_income - total_expenses) / total_income * 100, 2) if total_income > 0 else 0,
            'transaction_count': len(transactions),
            'income_by_category': income_by_category,
            'expense_by_category': dict(sorted_expenses),
            'top_expense_category': sorted_expenses[0] if sorted_expenses else None,
            'avg_transaction': round(statistics.mean([t.amount for t in transactions]), 2) if transactions else 0,
            'avg_expense': round(statistics.mean(expense_amounts), 2) if expense_amounts else 0,
            'median_expense': round(statistics.median(expense_amounts), 2) if expense_amounts else 0,
        }
        
        return summary
    
    def _get_period_transactions(self, period: str) -> List[Transaction]:
        """Get transactions for a specific period."""
        now = datetime.now()
        
        if period == 'today':
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == 'week':
            start_date = now - timedelta(days=now.weekday())
        elif period == 'month':
            start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        elif period == 'year':
            start_date = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            return self.transactions
        
        return self.get_transactions_by_date_range(start_date.isoformat(), now.isoformat())
    
    # Batch operations with context manager support
    def start_batch(self):
        """Start batch mode for multiple transactions."""
        self._batch_mode = True
        self._batch_backup = [t.to_dict() for t in self.transactions]
    
    def commit_batch(self):
        """Commit batch transactions."""
        self._batch_mode = False
        self._batch_backup = None
        self.save()
    
    def rollback_batch(self):
        """Rollback batch transactions."""
        if self._batch_backup:
            self.transactions = [Transaction.from_dict(t) for t in self._batch_backup]
        self._batch_mode = False
        self._batch_backup = None
    
    def save(self):
        """Save data to JSON file."""
        try:
            data = {
                'next_id': self.next_id,
                'transactions': [t.to_dict() for t in self.transactions],
                'budgets': [b.to_dict() for b in self.budgets]
            }
            
            with open(self.filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving data: {e}")
            raise
    
    def load(self):
        """Load data from JSON file."""
        if not Path(self.filename).exists():
            return
        
        try:
            with open(self.filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.next_id = data.get('next_id', 1)
                self.transactions = [
                    Transaction.from_dict(t) for t in data.get('transactions', [])
                ]
                self.budgets = [
                    Budget.from_dict(b) for b in data.get('budgets', [])
                ]
        except Exception as e:
            print(f"Error loading data: {e}")
            raise
    
    def export_to_csv(self, filename: str):
        """Export transactions to CSV."""
        if not self.transactions:
            print("No transactions to export")
            return
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            fieldnames = ['id', 'date', 'type', 'category', 'amount', 'description']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for t in sorted(self.transactions, key=lambda x: x.date):
                writer.writerow({
                    'id': t.id,
                    'date': t.date[:10],
                    'type': t.transaction_type,
                    'category': t.category,
                    'amount': t.amount,
                    'description': t.description
                })
        
        print(f"✓ Exported {len(self.transactions)} transactions to {filename}")


def display_menu():
    """Display main menu."""
    print("\n" + "="*60)
    print("PERSONAL FINANCE TRACKER")
    print("="*60)
    print("1. Add Income")
    print("2. Add Expense")
    print("3. View All Transactions")
    print("4. View Summary")
    print("5. Set Budget")
    print("6. View Budgets")
    print("7. Search Transactions")
    print("8. Delete Transaction")
    print("9. Export to CSV")
    print("10. Exit")
    print("="*60)


def add_income(tracker: FinanceTracker):
    """Add income transaction interactively."""
    print("\n--- Add Income ---")
    print("Categories:", ", ".join(Transaction.CATEGORIES['income']))
    
    try:
        amount = float(input("Amount: $"))
        category = input("Category: ").strip().lower()
        description = input("Description: ").strip()
        date = input("Date (YYYY-MM-DD, Enter for today): ").strip()
        
        tracker.add_transaction(
            amount=amount,
            category=category,
            description=description,
            transaction_type='income',
            date=date if date else None
        )
    except ValueError as e:
        print(f"✗ Error: {e}")


def add_expense(tracker: FinanceTracker):
    """Add expense transaction interactively."""
    print("\n--- Add Expense ---")
    print("Categories:", ", ".join(Transaction.CATEGORIES['expense']))
    
    try:
        amount = float(input("Amount: $"))
        category = input("Category: ").strip().lower()
        description = input("Description: ").strip()
        date = input("Date (YYYY-MM-DD, Enter for today): ").strip()
        
        tracker.add_transaction(
            amount=amount,
            category=category,
            description=description,
            transaction_type='expense',
            date=date if date else None
        )
    except ValueError as e:
        print(f"✗ Error: {e}")


def view_transactions(tracker: FinanceTracker):
    """View all transactions sorted by date."""
    transactions = sorted(tracker.transactions, key=lambda t: t.date, reverse=True)
    
    if not transactions:
        print("\nNo transactions found.")
        return
    
    print(f"\n--- All Transactions ({len(transactions)}) ---")
    print(f"Current Balance: ${tracker.get_balance():.2f}\n")
    
    for t in transactions[:20]:  # Show last 20
        print(t)


def view_summary(tracker: FinanceTracker):
    """View financial summary."""
    print("\n--- Summary Period ---")
    print("1. Today")
    print("2. This Week")
    print("3. This Month")
    print("4. This Year")
    print("5. All Time")
    
    choice = input("\nSelect period: ").strip()
    period_map = {'1': 'today', '2': 'week', '3': 'month', '4': 'year', '5': 'all'}
    period = period_map.get(choice, 'all')
    
    summary = tracker.get_summary(period)
    
    if 'error' in summary:
        print(f"\n{summary['error']}")
        return
    
    print(f"\n{'='*60}")
    print(f"FINANCIAL SUMMARY - {summary['period'].upper()}")
    print(f"{'='*60}")
    print(f"Total Income:     ${summary['total_income']:>10.2f}")
    print(f"Total Expenses:   ${summary['total_expenses']:>10.2f}")
    print(f"{'─'*60}")
    print(f"Net Savings:      ${summary['net_savings']:>10.2f}")
    print(f"Savings Rate:     {summary['savings_rate']:>9.1f}%")
    print(f"\nTransactions:     {summary['transaction_count']}")
    print(f"Avg Transaction:  ${summary['avg_transaction']:.2f}")
    print(f"Avg Expense:      ${summary['avg_expense']:.2f}")
    print(f"Median Expense:   ${summary['median_expense']:.2f}")
    
    if summary['expense_by_category']:
        print(f"\n{'─'*60}")
        print("Expenses by Category:")
        for category, amount in summary['expense_by_category'].items():
            percentage = (amount / summary['total_expenses'] * 100) if summary['total_expenses'] > 0 else 0
            print(f"  {category:15} ${amount:>8.2f}  ({percentage:>5.1f}%)")


def set_budget(tracker: FinanceTracker):
    """Set a budget interactively."""
    print("\n--- Set Budget ---")
    print("Categories:", ", ".join(Transaction.CATEGORIES['expense']))
    
    try:
        category = input("Category: ").strip().lower()
        limit = float(input("Budget limit: $"))
        period = input("Period (daily/weekly/monthly/yearly) [monthly]: ").strip().lower() or 'monthly'
        
        tracker.add_budget(category, limit, period)
    except ValueError as e:
        print(f"✗ Error: {e}")


def view_budgets(tracker: FinanceTracker):
    """View all budgets and spending."""
    if not tracker.budgets:
        print("\nNo budgets set.")
        return
    
    print("\n--- Budget Overview ---")
    for budget in tracker.budgets:
        spent = tracker.get_category_spending(budget.category, budget.period)
        remaining = budget.limit - spent
        percentage = (spent / budget.limit * 100) if budget.limit > 0 else 0
        
        status = "✓" if spent <= budget.limit else "✗"
        print(f"\n{status} {budget.category.upper()} ({budget.period})")
        print(f"   Budget:    ${budget.limit:.2f}")
        print(f"   Spent:     ${spent:.2f} ({percentage:.1f}%)")
        print(f"   Remaining: ${remaining:.2f}")


def main():
    """Main application."""
    print("Welcome to Personal Finance Tracker!")
    tracker = FinanceTracker()
    
    print(f"\nLoaded {len(tracker.transactions)} transactions")
    print(f"Current Balance: ${tracker.get_balance():.2f}")
    
    while True:
        display_menu()
        choice = input("\nEnter your choice: ").strip()
        
        if choice == '1':
            add_income(tracker)
        elif choice == '2':
            add_expense(tracker)
        elif choice == '3':
            view_transactions(tracker)
        elif choice == '4':
            view_summary(tracker)
        elif choice == '5':
            set_budget(tracker)
        elif choice == '6':
            view_budgets(tracker)
        elif choice == '7':
            category = input("\nEnter category to search: ").strip().lower()
            transactions = tracker.get_transactions_by_category(category)
            if transactions:
                print(f"\n{len(transactions)} transactions in '{category}':")
                for t in sorted(transactions, key=lambda x: x.date, reverse=True):
                    print(t)
            else:
                print(f"\nNo transactions found in '{category}'")
        elif choice == '8':
            try:
                tid = int(input("\nEnter transaction ID to delete: "))
                if tracker.delete_transaction(tid):
                    print("✓ Transaction deleted")
                else:
                    print("✗ Transaction not found")
            except ValueError:
                print("✗ Invalid ID")
        elif choice == '9':
            filename = input("\nEnter CSV filename: ").strip()
            if not filename.endswith('.csv'):
                filename += '.csv'
            tracker.export_to_csv(filename)
        elif choice == '10':
            print("\nThank you for using Personal Finance Tracker!")
            break
        else:
            print("\n✗ Invalid choice")


if __name__ == "__main__":
    main()


"""
Key Features:

* Decorators: @validate_amount, @log_transaction, @validate_date for validation and logging
* Context Managers: @contextmanager for batch transaction operations with rollback
* Classes: Transaction, Budget, and FinanceTracker with full OOP
* File I/O: JSON persistence with save/load, CSV export
* DateTime Operations: Date ranges, period calculations, transaction filtering
* Lambda Functions: Used in sorting/filtering throughout
* Data Validation: Amount, category, type, and date validation
* Statistics: Mean, median calculations for spending analysis
* Budget Tracking: Set budgets with warnings when exceeded
Demonstrates:

* Function decorators with @wraps
* Context manager with @contextmanager
* Lambda functions for sorting/filtering
* List/dict comprehensions
* DateTime arithmetic and formatting
* Statistics module usage
* Try-except error handling
"""