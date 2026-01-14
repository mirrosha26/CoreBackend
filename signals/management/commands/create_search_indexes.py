"""
Management command to create optimized search indexes for PostgreSQL.
Uses trigram indexes for fast ILIKE/icontains queries.
"""

from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'Create PostgreSQL search indexes with trigram support for fast text search'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show SQL without executing',
        )
        parser.add_argument(
            '--drop',
            action='store_true',
            help='Drop existing search indexes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        drop = options['drop']
        
        with connection.cursor() as cursor:
            # Enable pg_trgm extension for trigram indexes (faster ILIKE queries)
            if not dry_run:
                try:
                    cursor.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
                    self.stdout.write(self.style.SUCCESS('✓ pg_trgm extension enabled'))
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f'pg_trgm extension: {e}'))
            else:
                self.stdout.write('Would execute: CREATE EXTENSION IF NOT EXISTS pg_trgm;')
            
            # Define search indexes using GIN and trigram operators
            search_indexes = [
                # SignalCard name trigram index for fast partial matching
                {
                    'name': 'idx_signalcard_name_trgm',
                    'create_sql': '''
                        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_signalcard_name_trgm 
                        ON signals_signalcard USING gin (name gin_trgm_ops);
                    ''',
                    'drop_sql': 'DROP INDEX CONCURRENTLY IF EXISTS idx_signalcard_name_trgm;',
                    'description': 'SignalCard name trigram index (for fast ILIKE search)'
                },
                
                # SignalCard description trigram index
                {
                    'name': 'idx_signalcard_description_trgm',
                    'create_sql': '''
                        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_signalcard_description_trgm 
                        ON signals_signalcard USING gin (description gin_trgm_ops);
                    ''',
                    'drop_sql': 'DROP INDEX CONCURRENTLY IF EXISTS idx_signalcard_description_trgm;',
                    'description': 'SignalCard description trigram index'
                },
                
                # TeamMember name trigram index
                {
                    'name': 'idx_teammember_name_trgm',
                    'create_sql': '''
                        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_teammember_name_trgm 
                        ON signals_teammember USING gin (name gin_trgm_ops);
                    ''',
                    'drop_sql': 'DROP INDEX CONCURRENTLY IF EXISTS idx_teammember_name_trgm;',
                    'description': 'TeamMember name trigram index (for searching by team member names)'
                },
                
                # Person name trigram index (for founders/people)
                {
                    'name': 'idx_person_name_trgm',
                    'create_sql': '''
                        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_person_name_trgm 
                        ON signals_person USING gin (name gin_trgm_ops);
                    ''',
                    'drop_sql': 'DROP INDEX CONCURRENTLY IF EXISTS idx_person_name_trgm;',
                    'description': 'Person name trigram index (for searching by people/founders names)'
                },
                
                # TeamMember signal_card_id index for JOIN optimization
                {
                    'name': 'idx_teammember_signalcard_name',
                    'create_sql': '''
                        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_teammember_signalcard_name 
                        ON signals_teammember (signal_card_id, name);
                    ''',
                    'drop_sql': 'DROP INDEX CONCURRENTLY IF EXISTS idx_teammember_signalcard_name;',
                    'description': 'TeamMember composite index for JOIN and name filtering'
                },
                
                # Person-SignalCard ManyToMany index for JOIN optimization
                {
                    'name': 'idx_person_signalcard_m2m',
                    'create_sql': '''
                        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_person_signalcard_m2m 
                        ON signals_person_signal_cards (signalcard_id, person_id);
                    ''',
                    'drop_sql': 'DROP INDEX CONCURRENTLY IF EXISTS idx_person_signalcard_m2m;',
                    'description': 'Person-SignalCard ManyToMany index for efficient person search'
                },
                
                # LinkedinData name trigram index
                {
                    'name': 'idx_linkedindata_name_trgm',
                    'create_sql': '''
                        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_linkedindata_name_trgm 
                        ON signals_linkedindata USING gin (name gin_trgm_ops);
                    ''',
                    'drop_sql': 'DROP INDEX CONCURRENTLY IF EXISTS idx_linkedindata_name_trgm;',
                    'description': 'LinkedinData name trigram index (for searching LinkedIn profiles)'
                },
                
                # Signal indexes for search JOIN optimization
                {
                    'name': 'idx_signal_linkedin_data_id',
                    'create_sql': '''
                        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_signal_linkedin_data_id 
                        ON signals_signal (linkedin_data_id, signal_card_id) 
                        WHERE linkedin_data_id IS NOT NULL;
                    ''',
                    'drop_sql': 'DROP INDEX CONCURRENTLY IF EXISTS idx_signal_linkedin_data_id;',
                    'description': 'Signal linkedin_data_id partial index for search JOINs'
                },
                
                # Combined full-text search index (optional, for advanced search)
                {
                    'name': 'idx_signalcard_fulltext',
                    'create_sql': '''
                        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_signalcard_fulltext 
                        ON signals_signalcard USING gin (
                            to_tsvector('english', coalesce(name, '') || ' ' || coalesce(description, ''))
                        );
                    ''',
                    'drop_sql': 'DROP INDEX CONCURRENTLY IF EXISTS idx_signalcard_fulltext;',
                    'description': 'SignalCard full-text search index (optional, for advanced search)'
                },
            ]
            
            if drop:
                self.stdout.write(self.style.WARNING('\n=== DROPPING SEARCH INDEXES ===\n'))
                for index in search_indexes:
                    try:
                        if dry_run:
                            self.stdout.write(f"Would execute: {index['drop_sql']}")
                        else:
                            cursor.execute(index['drop_sql'])
                            self.stdout.write(self.style.SUCCESS(f"✓ Dropped {index['name']}"))
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"✗ Error dropping {index['name']}: {e}"))
            else:
                self.stdout.write(self.style.SUCCESS('\n=== CREATING SEARCH INDEXES ===\n'))
                for index in search_indexes:
                    self.stdout.write(f"\n{index['description']}:")
                    try:
                        if dry_run:
                            self.stdout.write(f"{index['create_sql']}")
                        else:
                            cursor.execute(index['create_sql'])
                            self.stdout.write(self.style.SUCCESS(f"✓ Created {index['name']}"))
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"✗ Error creating {index['name']}: {e}"))
            
            # Show index sizes
            if not dry_run and not drop:
                self.stdout.write(self.style.SUCCESS('\n=== INDEX SIZES ===\n'))
                cursor.execute("""
                    SELECT 
                        indexname,
                        pg_size_pretty(pg_relation_size(quote_ident(indexname)::regclass)) as size
                    FROM pg_indexes
                    WHERE indexname LIKE 'idx_%trgm%' OR indexname LIKE 'idx_signalcard_fulltext%'
                    ORDER BY pg_relation_size(quote_ident(indexname)::regclass) DESC;
                """)
                for row in cursor.fetchall():
                    self.stdout.write(f"  {row[0]}: {row[1]}")
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\n[DRY RUN] No changes were made'))
        else:
            self.stdout.write(self.style.SUCCESS('\n✓ Search index optimization complete!'))
            self.stdout.write(self.style.SUCCESS('\nSearch queries using ILIKE/icontains will now be much faster.'))

