# Frontend Integration Guide: Profit Projections for StockProduct Line Items

## Overview

The backend now provides comprehensive profit projection APIs that allow calculating expected profit for each StockProduct line item based on custom retail/wholesale sales scenarios. This enables users to model different sales strategies and make data-driven decisions.

## Backend Changes Summary

### New API Endpoints

1. **Individual Stock Product Projection**: `POST /inventory/api/profit-projections/stock-product/`
2. **Product-Level Aggregation**: `POST /inventory/api/profit-projections/product/`
3. **Bulk Projections**: `POST /inventory/api/profit-projections/bulk/`
4. **Available Scenarios**: `GET /inventory/api/profit-projections/scenarios/`

### Key Features

- **Custom Retail/Wholesale Percentages**: Input any combination (e.g., 70% retail / 30% wholesale)
- **Comprehensive Calculations**: Profit per unit, total profit, profit margins, weighted averages
- **Scenario Comparisons**: Always includes retail-only, wholesale-only, and mixed scenarios
- **Business-Scoped Access**: Proper permission controls
- **Input Validation**: Ensures percentages sum to 100%

## Frontend Changes Required

### 1. Add Profit Projection UI Components

#### Scenario Selection Controls

Add UI controls to let users select retail/wholesale percentages for each line item:

```javascript
// Example React component for scenario selection
const ProfitScenarioSelector = ({ stockProductId, onProjectionChange }) => {
  const [retailPercentage, setRetailPercentage] = useState(100);
  const [wholesalePercentage, setWholesalePercentage] = useState(0);
  const [projection, setProjection] = useState(null);

  const calculateProjection = async () => {
    try {
      const response = await api.post('/inventory/api/profit-projections/stock-product/', {
        stock_product_id: stockProductId,
        retail_percentage: retailPercentage,
        wholesale_percentage: wholesalePercentage
      });
      setProjection(response.data);
      onProjectionChange(response.data);
    } catch (error) {
      console.error('Failed to calculate projection:', error);
    }
  };

  return (
    <div className="profit-scenario-selector">
      <div className="percentage-inputs">
        <label>
          Retail %:
          <input
            type="number"
            min="0"
            max="100"
            value={retailPercentage}
            onChange={(e) => {
              const retail = parseFloat(e.target.value) || 0;
              setRetailPercentage(retail);
              setWholesalePercentage(100 - retail);
            }}
          />
        </label>
        <label>
          Wholesale %:
          <input
            type="number"
            min="0"
            max="100"
            value={wholesalePercentage}
            onChange={(e) => {
              const wholesale = parseFloat(e.target.value) || 0;
              setWholesalePercentage(wholesale);
              setRetailPercentage(100 - wholesale);
            }}
          />
        </label>
        <button onClick={calculateProjection}>Calculate</button>
      </div>

      {projection && (
        <div className="projection-results">
          <h4>Expected Profit: ${projection.requested_scenario.total_profit}</h4>
          <p>Avg Selling Price: ${projection.requested_scenario.avg_selling_price}</p>
          <p>Profit Margin: {projection.requested_scenario.profit_margin}%</p>
        </div>
      )}
    </div>
  );
};
```

#### Predefined Scenario Dropdown

Use the scenarios endpoint to provide quick selection options:

```javascript
const ScenarioDropdown = ({ onScenarioSelect }) => {
  const [scenarios, setScenarios] = useState([]);

  useEffect(() => {
    const loadScenarios = async () => {
      try {
        const response = await api.get('/inventory/api/profit-projections/scenarios/');
        setScenarios(response.data.scenarios);
      } catch (error) {
        console.error('Failed to load scenarios:', error);
      }
    };
    loadScenarios();
  }, []);

  return (
    <select onChange={(e) => {
      const selected = scenarios.find(s => s.id === e.target.value);
      if (selected) {
        onScenarioSelect(selected.retail_percentage, selected.wholesale_percentage);
      }
    }}>
      <option value="">Select Scenario...</option>
      {scenarios.map(scenario => (
        <option key={scenario.id} value={scenario.id}>
          {scenario.name}
        </option>
      ))}
    </select>
  );
};
```

### 2. Update Stock Items Table

Add two new read-only columns to the stock items table so the default view immediately shows expected profit if every unit is sold via either channel:

* **Retail Projected Profit** – bind to `retail_only.total_profit`
* **Wholesale Projected Profit** – bind to `wholesale_only.total_profit`

Fetch the projection payload once per row when the table data loads. A lightweight helper can hit the stock-product projection endpoint with `retail_percentage=100` / `wholesale_percentage=0` and cache results so the table renders quickly.

```javascript
// Minimal helper for table rows
async function loadBaselineProjections(stockProductId) {
  const cacheKey = `${stockProductId}-baseline`;
  if (projectionCache.has(cacheKey)) return projectionCache.get(cacheKey);

  const response = await api.post('/inventory/api/profit-projections/stock-product/', {
    stock_product_id: stockProductId,
    retail_percentage: 100,
    wholesale_percentage: 0,
  });

  projectionCache.set(cacheKey, response.data);
  return response.data;
}

// When shaping table data
const rows = await Promise.all(stockProducts.map(async (sp) => {
  const projection = await loadBaselineProjections(sp.id);
  return {
    ...sp,
    retailProjectedProfit: parseFloat(projection.retail_only.total_profit),
    wholesaleProjectedProfit: parseFloat(projection.wholesale_only.total_profit),
  };
}));
```

Render the new columns alongside existing fields:

```jsx
<Table.Column
  title="Retail projected profit"
  dataIndex="retailProjectedProfit"
  render={(value) => formatCurrency(value)}
/>;

<Table.Column
  title="Wholesale projected profit"
  dataIndex="wholesaleProjectedProfit"
  render={(value) => formatCurrency(value)}
/>;
```

### 3. Update Line Item Display

#### Enhanced Line Item Component

Modify your existing StockProduct line item components to include profit projection information:

```javascript
const StockProductLineItem = ({ stockProduct, onProjectionUpdate }) => {
  const [projection, setProjection] = useState(null);
  const [showScenarios, setShowScenarios] = useState(false);

  const handleProjectionChange = (newProjection) => {
    setProjection(newProjection);
    onProjectionUpdate(stockProduct.id, newProjection);
  };

  return (
    <div className="stock-product-line-item">
      <div className="basic-info">
        <span className="product-name">{stockProduct.product.name}</span>
        <span className="sku">{stockProduct.product.sku}</span>
        <span className="quantity">Qty: {stockProduct.quantity}</span>
      </div>

      <div className="pricing-info">
        <span>Cost: ${stockProduct.landed_unit_cost}</span>
        <span>Retail: ${stockProduct.retail_price}</span>
        <span>Wholesale: ${stockProduct.wholesale_price}</span>
      </div>

      <div className="profit-projection">
        <button
          onClick={() => setShowScenarios(!showScenarios)}
          className="projection-toggle"
        >
          {projection ? `$${projection.requested_scenario.total_profit}` : 'Calculate Profit'}
        </button>

        {showScenarios && (
          <ProfitScenarioSelector
            stockProductId={stockProduct.id}
            onProjectionChange={handleProjectionChange}
          />
        )}

        {projection && (
          <div className="projection-summary">
            <div className="current-scenario">
              <small>
                {projection.requested_scenario.retail_percentage}% retail /
                {projection.requested_scenario.wholesale_percentage}% wholesale
              </small>
            </div>
            <div className="profit-details">
              <span>Total Profit: ${projection.requested_scenario.total_profit}</span>
              <span>Margin: {projection.requested_scenario.profit_margin}%</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
```

### 4. Bulk Operations Support

#### Bulk Projection for Multiple Items

For scenarios where users want to project profits across multiple line items:

```javascript
const BulkProfitProjection = ({ stockProducts, onBulkUpdate }) => {
  const [projections, setProjections] = useState([]);
  const [isCalculating, setIsCalculating] = useState(false);

  const calculateBulkProjections = async (retailPct = 100, wholesalePct = 0) => {
    setIsCalculating(true);
    try {
      const bulkData = {
        projections: stockProducts.map(sp => ({
          stock_product_id: sp.id,
          retail_percentage: retailPct,
          wholesale_percentage: wholesalePct
        }))
      };

      const response = await api.post('/inventory/api/profit-projections/bulk/', bulkData);
      setProjections(response.data.projections);
      onBulkUpdate(response.data.projections);
    } catch (error) {
      console.error('Bulk projection failed:', error);
    } finally {
      setIsCalculating(false);
    }
  };

  const totalProjectedProfit = projections.reduce(
    (sum, p) => sum + parseFloat(p.requested_scenario.total_profit),
    0
  );

  return (
    <div className="bulk-profit-projection">
      <div className="bulk-controls">
        <h3>Bulk Profit Projection</h3>
        <div className="scenario-buttons">
          <button onClick={() => calculateBulkProjections(100, 0)}>
            All Retail
          </button>
          <button onClick={() => calculateBulkProjections(0, 100)}>
            All Wholesale
          </button>
          <button onClick={() => calculateBulkProjections(70, 30)}>
            70/30 Mix
          </button>
        </div>
      </div>

      {isCalculating && <div className="loading">Calculating projections...</div>}

      {projections.length > 0 && (
        <div className="bulk-results">
          <h4>Total Projected Profit: ${totalProjectedProfit.toFixed(2)}</h4>
          <div className="projections-list">
            {projections.map(proj => (
              <div key={proj.stock_product_id} className="projection-item">
                <span>{proj.product_name}</span>
                <span>${proj.requested_scenario.total_profit}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
```

### 5. Update Data Models and State Management

#### Add Projection Data to StockProduct Model

Update your frontend StockProduct model to include projection data:

```javascript
// Updated StockProduct interface
interface StockProduct {
  id: string;
  product: {
    id: string;
    name: string;
    sku: string;
  };
  quantity: number;
  landed_unit_cost: number;
  retail_price: number;
  wholesale_price: number;
  // Add projection data
  profitProjection?: {
    requested_scenario: ProfitScenario;
    retail_only: ProfitScenario;
    wholesale_only: ProfitScenario;
    mixed_scenarios: ProfitScenario[];
  };
}

interface ProfitScenario {
  retail_percentage: number;
  wholesale_percentage: number;
  retail_units: number;
  wholesale_units: number;
  avg_selling_price: number;
  profit_per_unit: number;
  profit_margin: number;
  total_profit: number;
}
```

#### State Management Updates

```javascript
// Redux slice example
const stockProductsSlice = createSlice({
  name: 'stockProducts',
  initialState: {
    items: [],
    projections: {}, // Map of stockProductId -> projection data
    bulkProjection: null,
  },
  reducers: {
    setStockProducts: (state, action) => {
      state.items = action.payload;
    },
    updateProjection: (state, action) => {
      const { stockProductId, projection } = action.payload;
      state.projections[stockProductId] = projection;
    },
    setBulkProjection: (state, action) => {
      state.bulkProjection = action.payload;
    },
  },
});
```

### 6. Error Handling and Validation

#### Input Validation

```javascript
const validatePercentages = (retail, wholesale) => {
  const total = retail + wholesale;
  if (total !== 100) {
    throw new Error('Retail and wholesale percentages must sum to 100%');
  }
  if (retail < 0 || retail > 100 || wholesale < 0 || wholesale > 100) {
    throw new Error('Percentages must be between 0 and 100');
  }
};
```

#### API Error Handling

```javascript
const handleProjectionError = (error) => {
  if (error.response?.status === 400) {
    // Validation error
    alert('Invalid percentages: ' + error.response.data.detail);
  } else if (error.response?.status === 404) {
    // Stock product not found
    alert('Stock product not found or access denied');
  } else {
    // Other error
    alert('Failed to calculate profit projection');
  }
};
```

### 7. Performance Optimizations

#### Debounced Calculations

For real-time updates as users adjust percentages:

```javascript
import { useCallback } from 'react';
import { debounce } from 'lodash';

const ProfitProjectionCalculator = ({ stockProductId }) => {
  const [retailPct, setRetailPct] = useState(100);
  const [wholesalePct, setWholesalePct] = useState(0);

  const debouncedCalculate = useCallback(
    debounce(async (retail, wholesale) => {
      try {
        const response = await api.post('/inventory/api/profit-projections/stock-product/', {
          stock_product_id: stockProductId,
          retail_percentage: retail,
          wholesale_percentage: wholesale
        });
        // Update UI with results
      } catch (error) {
        // Handle error
      }
    }, 300),
    [stockProductId]
  );

  const handlePercentageChange = (retail, wholesale) => {
    setRetailPct(retail);
    setWholesalePct(wholesale);
    debouncedCalculate(retail, wholesale);
  };

  // ... rest of component
};
```

#### Caching Projections

Cache projection results to avoid redundant API calls:

```javascript
const projectionCache = new Map();

const getCachedProjection = async (stockProductId, retailPct, wholesalePct) => {
  const cacheKey = `${stockProductId}-${retailPct}-${wholesalePct}`;

  if (projectionCache.has(cacheKey)) {
    return projectionCache.get(cacheKey);
  }

  const response = await api.post('/inventory/api/profit-projections/stock-product/', {
    stock_product_id: stockProductId,
    retail_percentage: retailPct,
    wholesale_percentage: wholesalePct
  });

  projectionCache.set(cacheKey, response.data);
  return response.data;
};
```

## API Response Examples

### Individual Stock Product Projection

```json
{
  "stock_product_id": "uuid",
  "product_name": "Laptop Pro",
  "product_sku": "LAPTOP-001",
  "quantity": 100,
  "landed_unit_cost": "800.00",
  "retail_price": "1200.00",
  "wholesale_price": "1000.00",
  "requested_scenario": {
    "retail_percentage": "70.00",
    "wholesale_percentage": "30.00",
    "retail_units": "70.00",
    "wholesale_units": "30.00",
    "avg_selling_price": "1140.000",
    "profit_per_unit": "240.000",
    "profit_margin": "21.05",
    "total_profit": "24000.000"
  },
  "retail_only": { /* same structure */ },
  "wholesale_only": { /* same structure */ },
  "mixed_scenarios": [ /* array of scenarios */ ]
}
```

## Migration Strategy

1. **Phase 1**: Add profit projection UI components alongside existing displays
2. **Phase 2**: Implement individual line item projections
3. **Phase 3**: Add bulk operations and scenario comparisons
4. **Phase 4**: Optimize performance and add caching
5. **Phase 5**: Add advanced features (historical comparisons, export options)

## Testing Checklist

- [ ] Individual stock product projections work correctly
- [ ] Percentage validation prevents invalid inputs
- [ ] Bulk projections handle multiple items efficiently
- [ ] Error states are handled gracefully
- [ ] Performance is acceptable with large datasets
- [ ] Mobile responsiveness is maintained
- [ ] Accessibility requirements are met

## Questions for Backend Team

1. Should projections be cached server-side?
2. Are there rate limits on the projection endpoints?
3. How frequently should projection data be refreshed?
4. Are there plans for historical projection tracking?</content>
<parameter name="filePath">/home/teejay/Documents/Projects/pos/backend/docs/frontend-profit-projections-integration.md