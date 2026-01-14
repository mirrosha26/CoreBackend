# GraphQL App Documentation

## Overview

This GraphQL application provides a comprehensive API for the Veck platform, built with **Strawberry GraphQL** and **Django**. It offers advanced querying capabilities for signal cards, participants, categories, and user management with extensive performance optimizations and caching strategies.

## Architecture

### Core Components

```
graphql_app/
├── schema.py              # Main GraphQL schema with DjangoOptimizerExtension
├── queries.py             # All query resolvers (2,746 lines)
├── mutations.py           # All mutation resolvers (1,412 lines)
├── types.py               # GraphQL type definitions (1,427 lines)
├── performance.py         # Performance monitoring and metrics
├── query_complexity.py    # Query complexity analysis and limits
├── dataloaders.py         # DataLoader implementations for N+1 prevention
├── query_caching.py       # Query-level caching strategies
├── comprehensive_query_caching.py  # Advanced caching for complex queries
├── enhanced_prefetching.py         # Intelligent database prefetching
├── enhanced_bulk_loading.py        # Bulk loading optimizations
├── optimized_signal_resolver.py    # Optimized signal field resolver
├── optimized_user_context.py       # User context optimization
├── regional_mappings.py             # Geographic region mappings
├── views.py               # Django views for GraphQL endpoint
└── urls.py                # URL routing
```

### Key Features

- **Performance Monitoring** - Real-time query performance tracking
- **Query Complexity Analysis** - Prevents expensive operations
- **Multi-level Caching** - Query, field, and comprehensive caching
- **DataLoaders** - Efficient batch loading to prevent N+1 queries
- **Smart Prefetching** - Dynamic relationship loading based on GraphQL query
- **Privacy Controls** - Granular access control for private participants
- **Regional Filtering** - Geographic location grouping and filtering
- **User Preferences** - WEB2/WEB3/ALL display preference filtering
- **Advanced Search** - Full-text search with relevance scoring
- **Flexible Pagination** - Both traditional and Relay-style cursor pagination

## Main Query Types

### 1. Signal Cards (`signalCards`)

**Purpose**: Fetch paginated signal cards with advanced filtering and optimization

**Key Features**:

- Advanced filtering (categories, participants, stages, locations, etc.)
- Search with relevance scoring
- Folder support (`folder_key` parameter)
- Privacy filtering for private participants
- User display preferences (WEB2/WEB3/ALL)
- Intelligent caching based on query complexity

**Usage Example**:

```graphql
query GetSignalCards {
  signalCards(
    filters: {
      search: "AI startup"
      categories: ["1", "2"]
      stages: ["seed", "series_a"]
      featured: true
    }
    pagination: { page: 1, page_size: 20 }
    sort_by: LATEST_SIGNAL_DATE
    include_signals: true
  ) {
    nodes {
      id
      name
      slug
      description
      stage
      signals {
        id
        description
        participant {
          name
          type
        }
      }
    }
    total_count
    has_next_page
    current_page
  }
}
```

### 2. User Feed (`userFeed`)

**Purpose**: Personalized feed showing all accessible signal cards with user-specific filtering

**Key Features**:

- Shows ALL accessible content (not just followed participants)
- Privacy filtering respects user's participant access
- Personal feed preferences (categories, stages, locations)
- Option to bypass personal filters (`bypass_personal_filters`)
- Optimized for bulk loading with comprehensive caching

**Usage Example**:

```graphql
query GetUserFeed {
  userFeed(
    pagination: { page: 1, page_size: 20 }
    include_signals: true
    bypass_personal_filters: false
  ) {
    nodes {
      id
      name
      latest_signal_date
      signals {
        participant {
          name
          is_private
        }
      }
    }
    total_count
  }
}
```

### 3. Participants (`participants`)

**Purpose**: Paginated participants with smart search and privacy handling

**Key Features**:

- Relay-style cursor pagination
- Smart search with fund inclusion logic
- Privacy filtering (public + user's private participants)
- Type filtering (funds, angels, investors, etc.)
- Advanced search logic that includes associated funds

**Usage Example**:

```graphql
query GetParticipants {
  participants(
    first: 20
    search: "andreessen"
    funds_only: false
    types: ["investor", "fund"]
  ) {
    edges {
      node {
        id
        name
        type
        is_private
        associated_with {
          id
          name
        }
      }
      cursor
    }
    page_info {
      has_next_page
      end_cursor
    }
    total_count
  }
}
```

### 4. Smart Participant Search (`smartParticipantSearch`)

**Purpose**: Advanced participant search that intelligently includes funds

**Key Features**:

- Searches individuals and automatically includes their associated funds
- Deduplication to avoid showing same fund multiple times
- Option to include/exclude individual participants
- Privacy-aware search results

### 5. Regional Locations (`regionalLocations`)

**Purpose**: Geographic filtering with regional groupings

**Key Features**:

- Groups countries into regions (North America, Europe, Asia, etc.)
- Only shows regions/countries that exist in the database
- Active state tracking for UI components
- Partial selection support for regions

**Usage Example**:

```graphql
query GetRegionalLocations {
  regionalLocations(active_locations: ["United States", "Canada"]) {
    regional_mappings {
      name
      slug
      countries
    }
    filter_options {
      name
      slug
      active
      is_region
      partially_active
    }
  }
}
```

### 6. Saved Filters (`savedFilters`)

**Purpose**: User's saved filter configurations

**Key Features**:

- Filtered by user's current signal display preference
- Pagination support
- Optional recent projects count computation
- Default filter identification

**Usage Example**:

```graphql
query GetSavedFilters {
  savedFilters(
    pagination: { page: 1, page_size: 10 }
    include_recent_counts: true
  ) {
    nodes {
      id
      name
      is_default
      categories {
        name
      }
      participants {
        name
      }
      recent_projects_count
    }
  }
}
```

## Advanced Features

### Performance Optimization

#### Query Complexity Analysis

- Automatic complexity scoring based on field weights
- Prevents expensive queries from overwhelming the system
- Configurable complexity limits and depth restrictions

#### Multi-level Caching Strategy

1. **Query-level caching** - Caches entire query results for expensive operations
2. **Field-level caching** - Caches individual field computations
3. **Comprehensive caching** - Advanced caching for complex feed queries

#### DataLoaders

- Batch loading for participants, categories, and signals
- Prevents N+1 query problems
- Automatic batching and deduplication

#### Enhanced Prefetching

- Dynamically determines relationships to prefetch based on GraphQL query
- Reduces database round trips
- Optimizes select_related and prefetch_related usage

### Privacy & Security

#### Privacy Filtering

- **Public participants**: Visible to all users
- **Private participants**: Only visible to users who created/requested them
- Consistent privacy logic across all queries

#### User Display Preferences

- **ALL**: Shows all signal cards
- **WEB2**: Excludes web3 categories and subcategories
- **WEB3**: Shows only web3 categories and subcategories

### Filtering System

#### Advanced Participant Filtering

```graphql
input ParticipantFilter {
  mode: ParticipantFilterMode # INCLUDE_ONLY, EXCLUDE_FROM_TYPE
  participantIds: [ID!]
  participantTypes: [String!]
}
```

#### Date Filtering

- Flexible date input supporting multiple formats (DD.MM.YYYY, YYYY-MM-DD, etc.)
- Custom FlexibleDate scalar for consistent date handling

#### Search Features

- Full-text search across multiple fields
- Relevance scoring for search results
- Search result ordering by relevance + secondary criteria

## Mutation Operations

### Card Management

- `saveCardToFolder` - Save cards to user folders
- `removeCardFromFolder` - Remove cards from folders
- `deleteCard` - Soft delete cards (adds to deleted list)
- `restoreCard` - Restore deleted cards

### Note Management

- `addNoteToCard` - Add notes to signal cards
- `updateCardNote` - Update existing notes
- `removeNoteFromCard` - Remove notes

### Filter Management

- `saveCurrentFilters` - Save current filter state
- `clearFilters` - Clear all active filters
- `updateFilter` - Update specific filter values
- `createSavedFilter` - Create new saved filter
- `updateSavedFilter` - Update existing saved filter
- `deleteSavedFilter` - Delete saved filter

### Folder Management

- `createUserFolder` - Create new user folders
- `updateUserFolder` - Update folder properties
- `deleteUserFolder` - Delete folders
- `setDefaultFolder` - Set default folder for user

## Usage Examples

### Complex Query with Multiple Features

```graphql
query ComplexSignalCardsQuery {
  signalCards(
    filters: {
      search: "AI fintech startup"
      categories: ["1", "5", "8"]
      participant_filter: {
        mode: EXCLUDE_FROM_TYPE
        participantTypes: ["angel", "investor"]
        participantIds: ["123", "456"]
      }
      stages: ["seed", "series_a"]
      locations: ["United States", "United Kingdom"]
      featured: true
      start_date: "01.01.2024"
      end_date: "31.12.2024"
      min_signals: 3
    }
    pagination: { page: 1, page_size: 20 }
    sort_by: LATEST_SIGNAL_DATE
    sort_order: DESC
    include_signals: true
  ) {
    nodes {
      id
      name
      slug
      description
      stage
      round_status
      location
      featured
      latest_signal_date
      signals(limit: 5) {
        id
        description
        created_at
        participant {
          id
          name
          type
          is_private
        }
        associated_participant {
          id
          name
          type
        }
      }
      categories {
        id
        name
        slug
      }
      is_saved
      is_noted
      note_text
    }
    total_count
    has_next_page
    has_previous_page
    current_page
    total_pages
  }
}
```

### Comprehensive User Context Query

```graphql
query UserDashboard {
  me {
    id
    username
    email
    signal_display_preference
  }

  userFeed(pagination: { page: 1, page_size: 10 }, include_signals: true) {
    nodes {
      id
      name
      stage
      signals(limit: 3) {
        participant {
          name
          type
        }
      }
    }
    total_count
  }

  savedFilters {
    nodes {
      id
      name
      is_default
      categories {
        name
      }
    }
  }

  categories {
    id
    name
    slug
  }
}
```

## Performance Considerations

### Query Complexity Limits

- Default max complexity: 1000
- Default max depth: 15
- Introspection complexity: 100

### Caching TTL Values

- Lightweight queries: No caching (computed directly)
- Moderate queries: 5 minutes
- Heavy queries: 15 minutes
- Comprehensive queries: 30 minutes

### Best Practices

1. **Use include_signals sparingly** - Only when you need signal data
2. **Limit pagination size** - Max 100 items per page
3. **Prefer specific filters** - More specific filters enable better caching
4. **Use cursor pagination** - For large result sets
5. **Monitor query complexity** - Check for complexity warnings in responses

## Error Handling

### Common Error Types

- `QueryComplexityError` - Query exceeds complexity limits
- `AuthenticationError` - User not authenticated for protected operations
- `ValidationError` - Invalid input parameters
- `PrivacyError` - Attempted access to private resources

### Error Response Format

```json
{
  "errors": [
    {
      "message": "Query complexity (1200) exceeds maximum allowed (1000)",
      "extensions": {
        "code": "QUERY_COMPLEXITY_ERROR",
        "complexity": 1200,
        "max_allowed": 1000
      }
    }
  ]
}
```

## Configuration

### Environment Variables

```python
# GraphQL Configuration
GRAPHQL_MAX_COMPLEXITY = 1000
GRAPHQL_MAX_DEPTH = 15
GRAPHQL_INTROSPECTION_COMPLEXITY = 100

# Caching Configuration
GRAPHQL_CACHE_TTL_MODERATE = 300  # 5 minutes
GRAPHQL_CACHE_TTL_HEAVY = 900     # 15 minutes
GRAPHQL_CACHE_TTL_COMPREHENSIVE = 1800  # 30 minutes

# Performance Monitoring
GRAPHQL_ENABLE_PERFORMANCE_MONITORING = True
GRAPHQL_LOG_SLOW_QUERIES = True
GRAPHQL_SLOW_QUERY_THRESHOLD = 1000  # milliseconds
```

## Testing

### GraphQL Playground

Access the GraphQL playground at `/graphql/` for interactive query testing and schema exploration.

### Performance Testing

Use the `@monitor_query_performance` decorator on resolvers to track:

- Execution time
- Database queries count
- Cache hit/miss ratios
- Memory usage

### Complexity Testing

Test query complexity with introspection:

```graphql
query IntrospectComplexity {
  __schema {
    queryType {
      fields {
        name
        type {
          name
        }
      }
    }
  }
}
```

This documentation covers the comprehensive GraphQL API built for the Veck platform, showcasing advanced features for performance, security, and user experience optimization.
