"""
File-Based Contact Management System
Demonstrates: Classes/OOP, file I/O, JSON/CSV parsing, CRUD operations, 
error handling, string manipulation
"""

import json
import csv
import os
from datetime import datetime
from typing import List, Optional, Dict


class Contact:
    """Represents a single contact with validation and formatting."""
    
    def __init__(self, name: str, phone: str, email: str, address: str = "", notes: str = ""):
        self.id = None
        self.name = self._validate_name(name)
        self.phone = self._validate_phone(phone)
        self.email = self._validate_email(email)
        self.address = address
        self.notes = notes
        self.created_at = datetime.now().isoformat()
        self.updated_at = self.created_at
    
    def _validate_name(self, name: str) -> str:
        """Validate and clean contact name."""
        name = name.strip()
        if not name or len(name) < 2:
            raise ValueError("Name must be at least 2 characters long")
        return name.title()
    
    def _validate_phone(self, phone: str) -> str:
        """Validate and format phone number."""
        # Remove all non-numeric characters
        cleaned = ''.join(filter(str.isdigit, phone))
        if len(cleaned) < 10:
            raise ValueError("Phone number must contain at least 10 digits")
        return cleaned
    
    def _validate_email(self, email: str) -> str:
        """Basic email validation."""
        email = email.strip().lower()
        if '@' not in email or '.' not in email.split('@')[1]:
            raise ValueError("Invalid email format")
        return email
    
    def update(self, **kwargs):
        """Update contact fields."""
        if 'name' in kwargs:
            self.name = self._validate_name(kwargs['name'])
        if 'phone' in kwargs:
            self.phone = self._validate_phone(kwargs['phone'])
        if 'email' in kwargs:
            self.email = self._validate_email(kwargs['email'])
        if 'address' in kwargs:
            self.address = kwargs['address']
        if 'notes' in kwargs:
            self.notes = kwargs['notes']
        self.updated_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict:
        """Convert contact to dictionary."""
        return {
            'id': self.id,
            'name': self.name,
            'phone': self.phone,
            'email': self.email,
            'address': self.address,
            'notes': self.notes,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Contact':
        """Create contact from dictionary."""
        contact = cls(
            name=data['name'],
            phone=data['phone'],
            email=data['email'],
            address=data.get('address', ''),
            notes=data.get('notes', '')
        )
        contact.id = data.get('id')
        contact.created_at = data.get('created_at', contact.created_at)
        contact.updated_at = data.get('updated_at', contact.updated_at)
        return contact
    
    def __str__(self) -> str:
        """String representation of contact."""
        return f"[{self.id}] {self.name} | {self.phone} | {self.email}"
    
    def __repr__(self) -> str:
        return f"Contact(id={self.id}, name='{self.name}')"


class ContactManager:
    """Manages contacts with file persistence (JSON and CSV support)."""
    
    def __init__(self, filename: str = "contacts.json"):
        self.filename = filename
        self.contacts: List[Contact] = []
        self.next_id = 1
        self.load()
    
    def add(self, contact: Contact) -> Contact:
        """Add a new contact (Create operation)."""
        contact.id = self.next_id
        self.contacts.append(contact)
        self.next_id += 1
        self.save()
        return contact
    
    def get(self, contact_id: int) -> Optional[Contact]:
        """Get contact by ID (Read operation)."""
        for contact in self.contacts:
            if contact.id == contact_id:
                return contact
        return None
    
    def get_all(self) -> List[Contact]:
        """Get all contacts (Read operation)."""
        return self.contacts.copy()
    
    def update(self, contact_id: int, **kwargs) -> Optional[Contact]:
        """Update contact by ID (Update operation)."""
        contact = self.get(contact_id)
        if contact:
            contact.update(**kwargs)
            self.save()
            return contact
        return None
    
    def delete(self, contact_id: int) -> bool:
        """Delete contact by ID (Delete operation)."""
        contact = self.get(contact_id)
        if contact:
            self.contacts.remove(contact)
            self.save()
            return True
        return False
    
    def search(self, query: str) -> List[Contact]:
        """Search contacts by name, phone, or email."""
        query = query.lower()
        results = []
        for contact in self.contacts:
            if (query in contact.name.lower() or 
                query in contact.phone or 
                query in contact.email.lower() or
                query in contact.address.lower()):
                results.append(contact)
        return results
    
    def save(self):
        """Save contacts to file (JSON or CSV based on extension)."""
        try:
            if self.filename.endswith('.json'):
                self._save_json()
            elif self.filename.endswith('.csv'):
                self._save_csv()
            else:
                raise ValueError("Unsupported file format. Use .json or .csv")
        except Exception as e:
            print(f"Error saving contacts: {e}")
            raise
    
    def _save_json(self):
        """Save contacts to JSON file."""
        data = {
            'next_id': self.next_id,
            'contacts': [contact.to_dict() for contact in self.contacts]
        }
        with open(self.filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def _save_csv(self):
        """Save contacts to CSV file."""
        with open(self.filename, 'w', newline='', encoding='utf-8') as f:
            if self.contacts:
                fieldnames = ['id', 'name', 'phone', 'email', 'address', 'notes', 
                            'created_at', 'updated_at']
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for contact in self.contacts:
                    writer.writerow(contact.to_dict())
    
    def load(self):
        """Load contacts from file."""
        if not os.path.exists(self.filename):
            return
        
        try:
            if self.filename.endswith('.json'):
                self._load_json()
            elif self.filename.endswith('.csv'):
                self._load_csv()
        except Exception as e:
            print(f"Error loading contacts: {e}")
            raise
    
    def _load_json(self):
        """Load contacts from JSON file."""
        with open(self.filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
            self.next_id = data.get('next_id', 1)
            self.contacts = [Contact.from_dict(c) for c in data.get('contacts', [])]
    
    def _load_csv(self):
        """Load contacts from CSV file."""
        with open(self.filename, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            contacts = []
            max_id = 0
            for row in reader:
                row['id'] = int(row['id']) if row['id'] else None
                contact = Contact.from_dict(row)
                contacts.append(contact)
                if contact.id and contact.id > max_id:
                    max_id = contact.id
            self.contacts = contacts
            self.next_id = max_id + 1
    
    def export_to_csv(self, filename: str):
        """Export contacts to a CSV file."""
        temp_filename = self.filename
        self.filename = filename
        self._save_csv()
        self.filename = temp_filename
        print(f"Exported {len(self.contacts)} contacts to {filename}")
    
    def export_to_json(self, filename: str):
        """Export contacts to a JSON file."""
        temp_filename = self.filename
        self.filename = filename
        self._save_json()
        self.filename = temp_filename
        print(f"Exported {len(self.contacts)} contacts to {filename}")


def display_menu():
    """Display the main menu."""
    print("\n" + "="*50)
    print("CONTACT MANAGEMENT SYSTEM")
    print("="*50)
    print("1. Add Contact")
    print("2. View All Contacts")
    print("3. Search Contact")
    print("4. Update Contact")
    print("5. Delete Contact")
    print("6. Export to CSV")
    print("7. Export to JSON")
    print("8. Exit")
    print("="*50)


def add_contact_interactive(manager: ContactManager):
    """Interactive contact creation."""
    print("\n--- Add New Contact ---")
    try:
        name = input("Name: ").strip()
        phone = input("Phone: ").strip()
        email = input("Email: ").strip()
        address = input("Address (optional): ").strip()
        notes = input("Notes (optional): ").strip()
        
        contact = Contact(name, phone, email, address, notes)
        manager.add(contact)
        print(f"\n✓ Contact added successfully! ID: {contact.id}")
    except ValueError as e:
        print(f"\n✗ Error: {e}")
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")


def view_all_contacts(manager: ContactManager):
    """Display all contacts."""
    contacts = manager.get_all()
    if not contacts:
        print("\nNo contacts found.")
        return
    
    print(f"\n--- All Contacts ({len(contacts)}) ---")
    for contact in contacts:
        print(f"\nID: {contact.id}")
        print(f"Name: {contact.name}")
        print(f"Phone: {contact.phone}")
        print(f"Email: {contact.email}")
        print(f"Address: {contact.address or 'N/A'}")
        print(f"Notes: {contact.notes or 'N/A'}")
        print(f"Created: {contact.created_at}")
        print("-" * 40)


def search_contacts(manager: ContactManager):
    """Search for contacts."""
    query = input("\nEnter search query (name/phone/email/address): ").strip()
    if not query:
        print("Search query cannot be empty.")
        return
    
    results = manager.search(query)
    if not results:
        print(f"\nNo contacts found matching '{query}'")
        return
    
    print(f"\n--- Search Results ({len(results)}) ---")
    for contact in results:
        print(f"\n{contact}")
        print(f"Address: {contact.address or 'N/A'}")
        print(f"Notes: {contact.notes or 'N/A'}")


def update_contact_interactive(manager: ContactManager):
    """Interactive contact update."""
    try:
        contact_id = int(input("\nEnter contact ID to update: "))
        contact = manager.get(contact_id)
        
        if not contact:
            print(f"\n✗ Contact with ID {contact_id} not found.")
            return
        
        print(f"\nCurrent contact: {contact}")
        print("Leave blank to keep current value.")
        
        updates = {}
        name = input(f"Name [{contact.name}]: ").strip()
        if name:
            updates['name'] = name
        
        phone = input(f"Phone [{contact.phone}]: ").strip()
        if phone:
            updates['phone'] = phone
        
        email = input(f"Email [{contact.email}]: ").strip()
        if email:
            updates['email'] = email
        
        address = input(f"Address [{contact.address}]: ").strip()
        if address:
            updates['address'] = address
        
        notes = input(f"Notes [{contact.notes}]: ").strip()
        if notes:
            updates['notes'] = notes
        
        if updates:
            manager.update(contact_id, **updates)
            print("\n✓ Contact updated successfully!")
        else:
            print("\nNo changes made.")
    
    except ValueError as e:
        print(f"\n✗ Error: {e}")
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")


def delete_contact_interactive(manager: ContactManager):
    """Interactive contact deletion."""
    try:
        contact_id = int(input("\nEnter contact ID to delete: "))
        contact = manager.get(contact_id)
        
        if not contact:
            print(f"\n✗ Contact with ID {contact_id} not found.")
            return
        
        print(f"\nContact to delete: {contact}")
        confirm = input("Are you sure? (yes/no): ").strip().lower()
        
        if confirm == 'yes':
            manager.delete(contact_id)
            print("\n✓ Contact deleted successfully!")
        else:
            print("\nDeletion cancelled.")
    
    except ValueError as e:
        print(f"\n✗ Error: {e}")


def main():
    """Main application loop."""
    print("Welcome to Contact Management System!")
    
    # Choose storage format
    print("\nSelect storage format:")
    print("1. JSON (default)")
    print("2. CSV")
    choice = input("Enter choice (1 or 2): ").strip()
    
    filename = "contacts.json" if choice != "2" else "contacts.csv"
    manager = ContactManager(filename)
    
    print(f"\nUsing {filename} for storage.")
    print(f"Loaded {len(manager.get_all())} existing contacts.")
    
    while True:
        display_menu()
        choice = input("\nEnter your choice (1-8): ").strip()
        
        if choice == '1':
            add_contact_interactive(manager)
        elif choice == '2':
            view_all_contacts(manager)
        elif choice == '3':
            search_contacts(manager)
        elif choice == '4':
            update_contact_interactive(manager)
        elif choice == '5':
            delete_contact_interactive(manager)
        elif choice == '6':
            filename = input("Enter CSV filename: ").strip()
            if not filename.endswith('.csv'):
                filename += '.csv'
            manager.export_to_csv(filename)
        elif choice == '7':
            filename = input("Enter JSON filename: ").strip()
            if not filename.endswith('.json'):
                filename += '.json'
            manager.export_to_json(filename)
        elif choice == '8':
            print("\nThank you for using Contact Management System!")
            break
        else:
            print("\n✗ Invalid choice. Please try again.")


if __name__ == "__main__":
    main()


"""
Key Features:

* OOP Design: Contact and ContactManager classes with encapsulation
* CRUD Operations: Create, Read, Update, Delete contacts
* Dual Format Support: Save/load from JSON or CSV files
* Validation: Email, phone, and name validation with error handling
* Search Functionality: Search across all contact fields
* Export Options: Export to both JSON and CSV formats
* Interactive CLI: Full menu-driven interface

Demonstrates:

* Classes with magic methods (__str__, __repr__)
* Class methods and static validation
* File I/O with both JSON and CSV
* Exception handling throughout
* String manipulation and formatting
* Type hints for better code quality
* DateTime operations for timestamps
"""