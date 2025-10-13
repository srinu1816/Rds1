from flask import Flask, jsonify, render_template, request
import math
import random
import os
import pymysql
from datetime import datetime
import time
import logging
import traceback

app = Flask(__name__)

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/home/ec2-user/app/app.log')
    ]
)
logger = logging.getLogger(__name__)

# Database configuration
DB_CONFIG = {
    'host': 'coupon-db.c18swy2galw4.eu-west-1.rds.amazonaws.com',
    'user': 'admin',
    'password': 'CouponApp123!',
    'database': 'coupon-db',
    'port': 3306,
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor,
    'connect_timeout': 30,
    'autocommit': True
}

def get_db_connection():
    """Create database connection with detailed error reporting"""
    try:
        logger.info(f"Attempting to connect to database: {DB_CONFIG['host']}")
        connection = pymysql.connect(**DB_CONFIG)
        logger.info("✅ Database connection successful")
        return connection
    except pymysql.MySQLError as e:
        logger.error(f"❌ MySQL connection error: {e}")
        logger.error(f"❌ Error code: {e.args[0]}")
        logger.error(f"❌ Error message: {e.args[1]}")
        return None
    except Exception as e:
        logger.error(f"❌ Unexpected connection error: {e}")
        logger.error(traceback.format_exc())
        return None

def init_database():
    """Initialize database tables"""
    logger.info("🔄 Starting database initialization...")
    connection = get_db_connection()
    if not connection:
        logger.error("💥 Cannot initialize database - no connection")
        return False
    
    try:
        with connection.cursor() as cursor:
            logger.info("Creating coupons table...")
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS coupons (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    coupon_code VARCHAR(50) NOT NULL UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    used BOOLEAN DEFAULT FALSE,
                    used_at TIMESTAMP NULL
                )
            ''')
            
            logger.info("Creating usage_logs table...")
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS usage_logs (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    coupon_code VARCHAR(50) NOT NULL,
                    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    ip_address VARCHAR(45)
                )
            ''')
            
        connection.commit()
        logger.info("✅ Database tables initialized successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        logger.error(traceback.format_exc())
        return False
    finally:
        connection.close()

def generate_coupon_code():
    """Generate a unique coupon code"""
    return ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=8))

def simulate_cpu_load():
    """Simulate moderate CPU load"""
    for i in range(1, 10000):  # Reduced for debugging
        math.sqrt(i)

@app.route('/')
def home():
    """Main page route"""
    try:
        logger.info("Home route accessed")
        
        # Simulate moderate CPU load
        simulate_cpu_load()
        
        # Generate coupon
        coupon = generate_coupon_code()
        logger.info(f"🎫 Generated coupon: {coupon}")
        
        # Store coupon in database
        connection = get_db_connection()
        db_status = "connected" if connection else "disconnected"
        
        if connection:
            try:
                with connection.cursor() as cursor:
                    # Insert coupon
                    cursor.execute(
                        'INSERT IGNORE INTO coupons (coupon_code) VALUES (%s)',
                        (coupon,)
                    )
                    
                    # Log generation
                    ip_address = request.remote_addr or 'unknown'
                    cursor.execute(
                        'INSERT INTO usage_logs (coupon_code, ip_address) VALUES (%s, %s)',
                        (coupon, ip_address)
                    )
                    
                connection.commit()
                logger.info(f"✅ Coupon {coupon} stored in database")
                
            except Exception as e:
                logger.error(f"❌ Failed to store coupon: {e}")
                logger.error(traceback.format_exc())
                db_status = "error"
            finally:
                connection.close()
        else:
            logger.warning("⚠️ No database connection available - coupon not stored")
        
        return render_template('index.html', coupon=coupon, status="generated", db_status=db_status)
    
    except Exception as e:
        logger.error(f"💥 Critical error in home route: {e}")
        logger.error(traceback.format_exc())
        return f"Internal Server Error: {str(e)}", 500

@app.route('/generate')
def generate_coupon():
    """API endpoint to generate a new coupon"""
    try:
        simulate_cpu_load()
        coupon = generate_coupon_code()
        
        connection = get_db_connection()
        db_status = "connected" if connection else "disconnected"
        
        if connection:
            try:
                with connection.cursor() as cursor:
                    cursor.execute(
                        'INSERT IGNORE INTO coupons (coupon_code) VALUES (%s)',
                        (coupon,)
                    )
                    
                    ip_address = request.remote_addr or 'unknown'
                    cursor.execute(
                        'INSERT INTO usage_logs (coupon_code, ip_address) VALUES (%s, %s)',
                        (coupon, ip_address)
                    )
                    
                connection.commit()
            except Exception as e:
                logger.error(f"❌ Failed to store coupon: {e}")
                db_status = "error"
            finally:
                connection.close()
        
        return jsonify({
            'coupon': coupon,
            'status': 'generated',
            'database': db_status,
            'timestamp': datetime.now().isoformat()
        })
    
    except Exception as e:
        logger.error(f"💥 Error in generate route: {e}")
        logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@app.route('/stats')
def stats():
    """Get coupon statistics"""
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({
                'error': 'Database connection failed', 
                'database_status': 'disconnected'
            }), 500
        
        with connection.cursor() as cursor:
            # Total coupons
            cursor.execute('SELECT COUNT(*) as total FROM coupons')
            total = cursor.fetchone()['total']
            
            # Used coupons
            cursor.execute('SELECT COUNT(*) as used FROM coupons WHERE used = TRUE')
            used = cursor.fetchone()['used']
            
            # Today's coupons
            cursor.execute('SELECT COUNT(*) as today FROM coupons WHERE DATE(created_at) = CURDATE()')
            today = cursor.fetchone()['today']
            
        connection.close()
        
        return jsonify({
            'total_coupons': total,
            'used_coupons': used,
            'today_coupons': today,
            'available_coupons': total - used,
            'database_status': 'connected'
        })
    
    except Exception as e:
        logger.error(f"💥 Error in stats route: {e}")
        logger.error(traceback.format_exc())
        return jsonify({'error': str(e), 'database_status': 'error'}), 500

@app.route('/health')
def health():
    """Health check endpoint"""
    try:
        connection = get_db_connection()
        db_status = "connected" if connection else "disconnected"
        
        db_test = False
        if connection:
            try:
                with connection.cursor() as cursor:
                    cursor.execute('SELECT 1 as test')
                    result = cursor.fetchone()
                    db_test = result['test'] == 1
                connection.close()
            except Exception as e:
                logger.error(f"Database test failed: {e}")
                db_status = "error"
        
        return jsonify({
            'status': 'healthy' if db_status == 'connected' and db_test else 'unhealthy', 
            'database': db_status,
            'database_test': db_test,
            'timestamp': datetime.now().isoformat()
        })
    
    except Exception as e:
        logger.error(f"💥 Error in health route: {e}")
        return jsonify({'status': 'error', 'error': str(e)}), 500

@app.route('/debug')
def debug():
    """Debug endpoint to check system status"""
    try:
        connection = get_db_connection()
        
        debug_info = {
            'flask_app': 'running',
            'database_connection': 'connected' if connection else 'failed',
            'timestamp': datetime.now().isoformat(),
            'python_version': os.sys.version,
            'environment_vars': {
                'DB_HOST': DB_CONFIG['host'],
                'DB_NAME': DB_CONFIG['database'],
                'DB_USER': DB_CONFIG['user'],
                'DB_PORT': DB_CONFIG['port']
            }
        }
        
        if connection:
            try:
                with connection.cursor() as cursor:
                    # Check if tables exist
                    cursor.execute("SHOW TABLES LIKE 'coupons'")
                    debug_info['coupons_table'] = 'exists' if cursor.fetchone() else 'missing'
                    
                    cursor.execute("SHOW TABLES LIKE 'usage_logs'")
                    debug_info['usage_logs_table'] = 'exists' if cursor.fetchone() else 'missing'
                    
                    # Count records
                    cursor.execute("SELECT COUNT(*) as count FROM coupons")
                    debug_info['coupons_count'] = cursor.fetchone()['count']
                    
                connection.close()
            except Exception as e:
                debug_info['database_query_error'] = str(e)
        
        return jsonify(debug_info)
    
    except Exception as e:
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500

# Initialize database when app starts
if __name__ == '__main__':
    logger.info("🚀 Starting Coupon Application...")
    logger.info(f"📊 Database Host: {DB_CONFIG['host']}")
    logger.info(f"🔑 Database Name: {DB_CONFIG['database']}")
    
    # Initialize database
    if init_database():
        logger.info("✅ Database initialization completed")
    else:
        logger.error("❌ Database initialization failed")
    
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"🌐 Starting Flask application on port {port}")
    
    # Run with debug enabled to see detailed errors
    app.run(host='0.0.0.0', port=port, debug=True)
    
    app.run(host='0.0.0.0', port=port, debug=debug)
