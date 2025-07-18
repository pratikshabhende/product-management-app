import os
import sys
import subprocess
from pybuilder.core import use_plugin, init, Author, after, task

# Core plugins
use_plugin("python.core")
use_plugin("python.unittest")
use_plugin("python.install_dependencies")
use_plugin("python.coverage")
use_plugin("python.distutils")

# Project information
name = "product_management"
version = "1.0.0"
summary = "FastAPI Product Management API"
description = "A RESTful API for managing products using FastAPI and SQLAlchemy"
authors = [Author("Project Team", "")]
license = "MIT"
url = "https://gitlab.com/your-group/product-management"

@init
def set_properties(project):
    # Source directories
    project.set_property("dir_source_main_python", "src/main/python")
    project.set_property("dir_source_unittest_python", "src/unittest/python")
    
    # Dependencies
    project.depends_on("fastapi")
    project.depends_on("sqlalchemy")
    project.depends_on("python-dotenv")
    project.depends_on("pydantic")
    project.depends_on("uvicorn")
    project.build_depends_on("httpx")
    
    # Test settings
    project.set_property("unittest_module_glob", "test_*")
    project.set_property("unittest_test_method_prefix", "test")
    project.set_property("unittest_test_file_glob", "test_*.py")
    project.set_property("unittest_always_verbose", True)
    
    # Coverage settings
    project.set_property("coverage_break_build", False)
    project.set_property("coverage_threshold_warn", 90)
    project.set_property("coverage_html", True)
    project.set_property("coverage_xml", True)
    
    # Distribution settings
    project.set_property("distutils_console_scripts", ["product-api = app:run_app"])
    project.set_property("distutils_packages", ["src", "src.main", "src.main.python"])
    project.set_property("distutils_commands", ["sdist", "bdist_wheel"])
    
    # Build settings
    project.set_property("dir_dist", "target/dist")
    project.set_property("dir_reports", "target/reports")

@task
def run(project, logger):
    """Run the FastAPI application"""
    logger.info("Starting FastAPI application...")
    try:
        # Run the application using uvicorn
        cmd = [sys.executable, "-m", "uvicorn", "app:app", "--reload", "--host", "0.0.0.0", "--port", "8000"]
        logger.info(f"Running command: {' '.join(cmd)}")
        subprocess.run(cmd, cwd=project.expand_path("$dir_source_main_python"))
    except Exception as e:
        logger.error(f"Error running FastAPI application: {e}")

@after('publish')
def create_pip_installable_zip(project, logger):
    """Ensure a pip-installable .zip is created after publish."""
    dist_dir = os.path.join(project.basedir, 'target', 'dist')
    setup_py = os.path.join(dist_dir, 'setup.py')
    if not os.path.exists(setup_py):
        logger.error(f"setup.py not found in {dist_dir}, cannot create .zip sdist.")
        return
    logger.info("Running: python setup.py sdist --formats=zip in target/dist")
    result = subprocess.run([sys.executable, 'setup.py', 'sdist', '--formats=zip'], cwd=dist_dir, capture_output=True, text=True)
    if result.returncode == 0:
        logger.info("Successfully created pip-installable .zip file.")
    else:
        logger.error(f"Failed to create .zip: {result.stderr}")
