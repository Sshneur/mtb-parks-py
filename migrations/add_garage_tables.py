def migrate():
    from database.connection import get_connection
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.executescript("""
            ALTER TABLE bikes ADD COLUMN bike_type TEXT DEFAULT 'mtb';
        """)
    except Exception:
        pass
    try:
        cursor = conn.cursor()
        cursor.executescript("""
            ALTER TABLE bikes ADD COLUMN suspension_type TEXT DEFAULT 'front_rear';
        """)
    except Exception:
        pass
    try:
        cursor = conn.cursor()
        cursor.executescript("""
            ALTER TABLE bikes ADD COLUMN fork_brand TEXT;
        """)
    except Exception:
        pass
    try:
        cursor = conn.cursor()
        cursor.executescript("""
            ALTER TABLE bikes ADD COLUMN fork_model TEXT;
        """)
    except Exception:
        pass
    try:
        cursor = conn.cursor()
        cursor.executescript("""
            ALTER TABLE bikes ADD COLUMN fork_pressure_psi REAL;
        """)
    except Exception:
        pass
    try:
        cursor = conn.cursor()
        cursor.executescript("""
            ALTER TABLE bikes ADD COLUMN fork_rebound_clicks INTEGER;
        """)
    except Exception:
        pass
    try:
        cursor = conn.cursor()
        cursor.executescript("""
            ALTER TABLE bikes ADD COLUMN fork_compression_clicks INTEGER;
        """)
    except Exception:
        pass
    try:
        cursor = conn.cursor()
        cursor.executescript("""
            ALTER TABLE bikes ADD COLUMN fork_sag_mm REAL;
        """)
    except Exception:
        pass
    try:
        cursor = conn.cursor()
        cursor.executescript("""
            ALTER TABLE bikes ADD COLUMN shock_brand TEXT;
        """)
    except Exception:
        pass
    try:
        cursor = conn.cursor()
        cursor.executescript("""
            ALTER TABLE bikes ADD COLUMN shock_model TEXT;
        """)
    except Exception:
        pass
    try:
        cursor = conn.cursor()
        cursor.executescript("""
            ALTER TABLE bikes ADD COLUMN shock_pressure_psi REAL;
        """)
    except Exception:
        pass
    try:
        cursor = conn.cursor()
        cursor.executescript("""
            ALTER TABLE bikes ADD COLUMN shock_rebound_clicks INTEGER;
        """)
    except Exception:
        pass
    try:
        cursor = conn.cursor()
        cursor.executescript("""
            ALTER TABLE bikes ADD COLUMN shock_compression_clicks INTEGER;
        """)
    except Exception:
        pass
    try:
        cursor = conn.cursor()
        cursor.executescript("""
            ALTER TABLE bikes ADD COLUMN shock_sag_mm REAL;
        """)
    except Exception:
        pass
    try:
        cursor = conn.cursor()
        cursor.executescript("""
            ALTER TABLE bikes ADD COLUMN front_tire_width_mm REAL;
        """)
    except Exception:
        pass
    try:
        cursor = conn.cursor()
        cursor.executescript("""
            ALTER TABLE bikes ADD COLUMN front_tire_pressure_psi REAL;
        """)
    except Exception:
        pass
    try:
        cursor = conn.cursor()
        cursor.executescript("""
            ALTER TABLE bikes ADD COLUMN rear_tire_width_mm REAL;
        """)
    except Exception:
        pass
    try:
        cursor = conn.cursor()
        cursor.executescript("""
            ALTER TABLE bikes ADD COLUMN rear_tire_pressure_psi REAL;
        """)
    except Exception:
        pass
    try:
        cursor = conn.cursor()
        cursor.executescript("""
            ALTER TABLE bikes ADD COLUMN wheel_size TEXT DEFAULT '29';
        """)
    except Exception:
        pass
    try:
        cursor = conn.cursor()
        cursor.executescript("""
            ALTER TABLE bikes ADD COLUMN groupset TEXT;
        """)
    except Exception:
        pass
    try:
        cursor = conn.cursor()
        cursor.executescript("""
            ALTER TABLE bikes ADD COLUMN brakes TEXT;
        """)
    except Exception:
        pass
    try:
        cursor = conn.cursor()
        cursor.executescript("""
            ALTER TABLE bikes ADD COLUMN rotor_size_front_mm INTEGER;
        """)
    except Exception:
        pass
    try:
        cursor = conn.cursor()
        cursor.executescript("""
            ALTER TABLE bikes ADD COLUMN rotor_size_rear_mm INTEGER;
        """)
    except Exception:
        pass
    try:
        cursor = conn.cursor()
        cursor.executescript("""
            ALTER TABLE bikes ADD COLUMN handlebar_width_mm INTEGER;
        """)
    except Exception:
        pass
    try:
        cursor = conn.cursor()
        cursor.executescript("""
            ALTER TABLE bikes ADD COLUMN stem_length_mm INTEGER;
        """)
    except Exception:
        pass
    try:
        cursor = conn.cursor()
        cursor.executescript("""
            ALTER TABLE bikes ADD COLUMN dropper_travel_mm INTEGER;
        """)
    except Exception:
        pass
    try:
        cursor = conn.cursor()
        cursor.executescript("""
            ALTER TABLE bikes ADD COLUMN fork_travel_mm INTEGER;
        """)
    except Exception:
        pass
    try:
        cursor = conn.cursor()
        cursor.executescript("""
            ALTER TABLE bikes ADD COLUMN shock_travel_mm INTEGER;
        """)
    except Exception:
        pass
    try:
        cursor = conn.cursor()
        cursor.executescript("""
            ALTER TABLE bikes ADD COLUMN fork_damper TEXT;
        """)
    except Exception:
        pass
    try:
        cursor = conn.cursor()
        cursor.executescript("""
            ALTER TABLE bikes ADD COLUMN fork_hsc_clicks INTEGER;
        """)
    except Exception:
        pass
    try:
        cursor = conn.cursor()
        cursor.executescript("""
            ALTER TABLE bikes ADD COLUMN fork_lsc_clicks INTEGER;
        """)
    except Exception:
        pass
    try:
        cursor = conn.cursor()
        cursor.executescript("""
            ALTER TABLE bikes ADD COLUMN fork_hsr_clicks INTEGER;
        """)
    except Exception:
        pass
    try:
        cursor = conn.cursor()
        cursor.executescript("""
            ALTER TABLE bikes ADD COLUMN fork_lsr_clicks INTEGER;
        """)
    except Exception:
        pass
    try:
        cursor = conn.cursor()
        cursor.executescript("""
            ALTER TABLE bikes ADD COLUMN shock_damper TEXT;
        """)
    except Exception:
        pass
    try:
        cursor = conn.cursor()
        cursor.executescript("""
            ALTER TABLE bikes ADD COLUMN shock_hsc_clicks INTEGER;
        """)
    except Exception:
        pass
    try:
        cursor = conn.cursor()
        cursor.executescript("""
            ALTER TABLE bikes ADD COLUMN shock_lsc_clicks INTEGER;
        """)
    except Exception:
        pass
    try:
        cursor = conn.cursor()
        cursor.executescript("""
            ALTER TABLE bikes ADD COLUMN shock_hsr_clicks INTEGER;
        """)
    except Exception:
        pass
    try:
        cursor = conn.cursor()
        cursor.executescript("""
            ALTER TABLE bikes ADD COLUMN shock_lsr_clicks INTEGER;
        """)
    except Exception:
        pass
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
    print("Migration complete")
