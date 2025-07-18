import sys
import os
import unittest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Set test mode
os.environ['TEST_MODE'] = 'true'

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
sys.path.insert(0, project_root)

# Add main python directory to path
main_python_dir = os.path.join(project_root, 'src', 'main', 'python')
sys.path.insert(0, main_python_dir)

# Import the app module
from app import app, Base, Product, ProductCreate, ProductUpdate, get_db

# Create test database
TEST_DB_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool  # This ensures single connection for in-memory SQLite
)

# Create all tables in the engine
Base.metadata.create_all(bind=engine)

# Create session factory
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Override the get_db dependency
def override_get_db():
    try:
        db = TestingSessionLocal()
        db.execute(text('SELECT 1'))  # Test connection
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

# Create test client
client = TestClient(app)

class TestProductAPI(unittest.TestCase):
    """Test suite for Product API endpoints"""
    
    @classmethod
    def setUpClass(cls):
        # Create tables once for all tests
        Base.metadata.create_all(bind=engine)

    def setUp(self):
        # Clear all tables before each test
        with engine.begin() as conn:
            for table in reversed(Base.metadata.sorted_tables):
                conn.execute(text(f'DELETE FROM {table.name}'))
        # VACUUM must be run outside transaction
        with engine.connect() as conn:
            conn.execute(text('VACUUM'))
            conn.commit()

    @classmethod
    def tearDownClass(cls):
        # Drop all tables after all tests
        Base.metadata.drop_all(bind=engine)
    
    def test_create_product(self):
        """Test successful product creation"""
        response = client.post("/products", json={
            "name": "Pen",
            "description": "Blue ink pen",
            "price": 10.50
        })
        self.assertEqual(response.status_code, 201)
        json_data = response.json()
        self.assertEqual(json_data["msg"], "Product created successfully")
        self.assertIsInstance(json_data["id"], int)
        self.assertEqual(json_data["name"], "Pen")
        
        # Verify product was actually created
        get_response = client.get(f"/products/{json_data['id']}")
        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(get_response.json()["name"], "Pen")
        self.assertEqual(get_response.json()["price"], 10.50)
    
    def test_get_all_products(self):
        client.post("/products", json={"name": "Pencil", "description": "HB", "price": 5.0})
        response = client.get("/products")
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json(), list)
        self.assertGreaterEqual(len(response.json()), 1)
    
    def test_get_product_by_id(self):
        client.post("/products", json={"name": "Eraser", "description": "Rubber", "price": 2.0})
        response = client.get("/products/1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name"], "Eraser")
    
    def test_get_product_by_name(self):
        client.post("/products", json={"name": "Sharpener", "description": "Steel", "price": 3.0})
        response = client.get("/products/name/Sharpener")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name"], "Sharpener")
    
    def test_update_product_by_name(self):
        """Test successful product update"""
        # Create test product
        create_response = client.post("/products", json={
            "name": "Marker",
            "description": "Red",
            "price": 15.0
        })
        self.assertEqual(create_response.status_code, 201)
        
        # Update product
        update_response = client.put("/products/name/Marker", json={
            "description": "Black",
            "price": 20.0
        })
        self.assertEqual(update_response.status_code, 200)
        json_data = update_response.json()
        self.assertEqual(json_data["msg"], "Product updated successfully")
        self.assertEqual(set(json_data["updated_fields"]), {"description", "price"})
        
        # Verify updates
        get_response = client.get(f"/products/{json_data['id']}")
        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(get_response.json()["description"], "Black")
        self.assertEqual(get_response.json()["price"], 20.0)
    
    def test_delete_product(self):
        """Test successful product deletion"""
        # Create test product
        create_response = client.post("/products", json={
            "name": "Glue",
            "description": "Stick",
            "price": 8.0
        })
        self.assertEqual(create_response.status_code, 201)
        product_id = create_response.json()["id"]
        
        # Delete product
        delete_response = client.delete(f"/products/{product_id}")
        self.assertEqual(delete_response.status_code, 200)
        json_data = delete_response.json()
        self.assertEqual(json_data["msg"], "Product deleted successfully")
        self.assertEqual(json_data["id"], product_id)
        self.assertEqual(json_data["name"], "Glue")
        
        # Verify product is deleted
        get_response = client.get(f"/products/{product_id}")
        self.assertEqual(get_response.status_code, 404)
    
    def test_get_nonexistent_product(self):
        response = client.get("/products/9999")
        self.assertEqual(response.status_code, 404)
    
    def test_create_duplicate_product(self):
        client.post("/products", json={"name": "Scale", "description": "30cm", "price": 12.0})
        response = client.post("/products", json={"name": "Scale", "description": "15cm", "price": 8.0})
        self.assertEqual(response.status_code, 409)  # Conflict status code for duplicate
    
    def test_create_product_missing_fields(self):
        response = client.post("/products", json={"description": "No name", "price": 5.0})
        self.assertEqual(response.status_code, 422)  # FastAPI returns 422 for validation errors
    
    def test_update_nonexistent_product(self):
        response = client.put("/products/name/NonExistentProduct", json={"description": "New desc", "price": 25.0})
        self.assertEqual(response.status_code, 404)
    
    def test_get_product_by_nonexistent_name(self):
        response = client.get("/products/name/NonExistentProduct")
        self.assertEqual(response.status_code, 404)
    
    def test_partial_update_product(self):
        """Test partial updates with individual fields"""
        # Create test product
        create_response = client.post("/products", json={
            "name": "Notebook",
            "description": "Lined",
            "price": 30.0
        })
        self.assertEqual(create_response.status_code, 201)
        
        # Update only description
        desc_response = client.put("/products/name/Notebook", json={
            "description": "Graph paper"
        })
        self.assertEqual(desc_response.status_code, 200)
        self.assertEqual(set(desc_response.json()["updated_fields"]), {"description"})
        
        # Verify description update
        get_response = client.get("/products/name/Notebook")
        self.assertEqual(get_response.json()["description"], "Graph paper")
        self.assertEqual(get_response.json()["price"], 30.0)  # Price unchanged
        
        # Update only price
        price_response = client.put("/products/name/Notebook", json={
            "price": 25.0
        })
        self.assertEqual(price_response.status_code, 200)
        self.assertEqual(set(price_response.json()["updated_fields"]), {"price"})
        
        # Verify price update
        get_response = client.get("/products/name/Notebook")
        self.assertEqual(get_response.json()["description"], "Graph paper")  # Description unchanged
        self.assertEqual(get_response.json()["price"], 25.0)
    
    def test_delete_nonexistent_product(self):
        response = client.delete("/products/9999")
        self.assertEqual(response.status_code, 404)
    
    def test_partial_update_price_only(self):
        client.post("/products", json={"name": "Stapler", "description": "Metal", "price": 25.0})
        # Update only price
        response = client.put("/products/name/Stapler", json={"price": 22.5})
        self.assertEqual(response.status_code, 200)
        # Verify the update
        get_response = client.get("/products/name/Stapler")
        self.assertEqual(get_response.json()["description"], "Metal")  # Description unchanged
        self.assertEqual(get_response.json()["price"], 22.5)  # Price updated


class TestModels(unittest.TestCase):
    
    def setUp(self):
        # Create the tables before each test
        Base.metadata.create_all(bind=engine)
    
    def tearDown(self):
        # Drop the tables after each test
        Base.metadata.drop_all(bind=engine)
    
    def test_product_model_creation(self):
        # Use context manager for database session
        with TestingSessionLocal() as db:
            # Create a product using the SQLAlchemy model
            product = Product(name="Test Product", description="Test Description", price=15.99)
            db.add(product)
            db.commit()
            db.refresh(product)
            
            # Retrieve the product and verify
            saved_product = db.query(Product).filter(Product.name == "Test Product").first()
            self.assertIsNotNone(saved_product)
            self.assertEqual(saved_product.name, "Test Product")
            self.assertEqual(saved_product.description, "Test Description")
            self.assertEqual(saved_product.price, 15.99)
            
            # Test cascade delete
            db.delete(product)
            db.commit()
            deleted_product = db.query(Product).filter(Product.name == "Test Product").first()
            self.assertIsNone(deleted_product)
    
    def test_product_create_pydantic_model(self):
        """Test Pydantic model for creating products"""
        product_data = {"name": "Model Test", "description": "Testing Pydantic", "price": 25.99}
        product_model = ProductCreate(**product_data)
        
        self.assertEqual(product_model.name, "Model Test")
        self.assertEqual(product_model.description, "Testing Pydantic")
        self.assertEqual(float(product_model.price), 25.99)
    
    def test_product_update_pydantic_model(self):
        """Test Pydantic model for updating products"""
        update_data = {"description": "Updated Description", "price": 30.99}
        update_model = ProductUpdate(**update_data)
        
        self.assertEqual(update_model.description, "Updated Description")
        self.assertEqual(float(update_model.price), 30.99)
    
    def test_product_update_pydantic_model_partial(self):
        """Test partial updates with Pydantic model"""
        # Only description
        desc_update = ProductUpdate(description="Only Description")
        self.assertEqual(desc_update.description, "Only Description")
        self.assertIsNone(desc_update.price)
        
        # Only price
        price_update = ProductUpdate(price=45.99)
        self.assertIsNone(price_update.description)
        self.assertEqual(float(price_update.price), 45.99)


class TestErrorHandling(unittest.TestCase):
    """Test suite for API error handling"""
    
    @classmethod
    def setUpClass(cls):
        # Create tables once for all tests
        Base.metadata.create_all(bind=engine)
    
    def setUp(self):
        # Clear all tables before each test
        with engine.begin() as conn:
            for table in reversed(Base.metadata.sorted_tables):
                conn.execute(text(f'DELETE FROM {table.name}'))
        with engine.connect() as conn:
            conn.execute(text('VACUUM'))
            conn.commit()
    
    @classmethod
    def tearDownClass(cls):
        # Drop all tables after all tests
        Base.metadata.drop_all(bind=engine)
    
    def test_internal_server_error_handling(self):
        """Test 500 error handling with invalid SQL"""
        # Force an internal error by passing invalid data type
        response = client.post("/products", json={
            "name": "Test",
            "description": "Test",
            "price": "invalid"
        })
        self.assertEqual(response.status_code, 422)
    
    def test_concurrent_updates(self):
        """Test handling concurrent updates to same product"""
        # Create initial product
        client.post("/products", json={
            "name": "Concurrent",
            "description": "Test",
            "price": 10.0
        })
        
        # Simulate concurrent updates
        response1 = client.put("/products/name/Concurrent", json={"price": 20.0})
        response2 = client.put("/products/name/Concurrent", json={"price": 30.0})
        
        self.assertEqual(response1.status_code, 200)
        self.assertEqual(response2.status_code, 200)
        
        # Verify final state
        get_response = client.get("/products/name/Concurrent")
        self.assertEqual(get_response.json()["price"], 30.0)


class TestValidation(unittest.TestCase):
    """Test suite for input validation"""
    
    def test_product_name_required(self):
        # Test that product name is required
        with self.assertRaises(Exception):
            ProductCreate(description="Missing name", price=10.0)
    
    def test_product_price_required(self):
        # Test that product price is required
        with self.assertRaises(Exception):
            ProductCreate(name="Test", description="Missing price")
    
    def test_product_price_type(self):
        # Test that product price must be a number
        with self.assertRaises(Exception):
            ProductCreate(name="Test", description="Invalid price", price="not a number")
    
    def test_product_description_default(self):
        # Test that description defaults to empty string
        product = ProductCreate(name="Test", price=10.0)
        self.assertEqual(product.description, "")
    
    def test_product_price_negative(self):
        # Test creating product with negative price
        response = client.post("/products", json={"name": "Test", "description": "Test", "price": -10.0})
        self.assertEqual(response.status_code, 422)  # Should fail validation
    
    def test_product_name_too_long(self):
        # Test creating product with name > 120 chars
        long_name = "x" * 121
        response = client.post("/products", json={"name": long_name, "description": "Test", "price": 10.0})
        self.assertEqual(response.status_code, 422)  # Should fail validation
    
    def test_product_description_too_long(self):
        # Test creating product with description > 255 chars
        long_desc = "x" * 256
        response = client.post("/products", json={"name": "Test", "description": long_desc, "price": 10.0})
        self.assertEqual(response.status_code, 422)  # Should fail validation


class TestDatabaseSession(unittest.TestCase):
    """Test suite for database session management"""
    
    def setUp(self):
        # Create tables and clear data before each test
        Base.metadata.create_all(bind=engine)
        with engine.begin() as conn:
            for table in reversed(Base.metadata.sorted_tables):
                conn.execute(text(f'DELETE FROM {table.name}'))
        with engine.connect() as conn:
            conn.execute(text('VACUUM'))
            conn.commit()
    
    def tearDown(self):
        Base.metadata.drop_all(bind=engine)
    
    def test_get_db_yields_session(self):
        # Test that get_db yields a session
        db_gen = get_db()
        db = next(db_gen)
        
        # Check that we got a valid session
        self.assertTrue(hasattr(db, 'query'))
        self.assertTrue(hasattr(db, 'add'))
        self.assertTrue(hasattr(db, 'commit'))
        
        # Clean up
        try:
            next(db_gen)
        except StopIteration:
            pass  # Expected behavior when generator is exhausted


if __name__ == '__main__':
    # Run tests with verbosity
    unittest.main(verbosity=2)
