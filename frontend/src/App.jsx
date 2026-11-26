import { useEffect, useState } from 'react'
import './App.css'

const navItems = [
  ['overview', 'Overview'],
  ['products', 'Products'],
  ['orders', 'Orders'],
  ['customers', 'Customers'],
]

async function api(path, options) {
  const response = await fetch(path, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...options?.headers },
  })
  const data = await response.json()
  if (!response.ok) {
    throw new Error(data.error?.message || 'The request failed')
  }
  return data
}

function Icon({ name }) {
  const paths = {
    grid: <><rect x="3" y="3" width="7" height="7" rx="2"/><rect x="14" y="3" width="7" height="7" rx="2"/><rect x="3" y="14" width="7" height="7" rx="2"/><rect x="14" y="14" width="7" height="7" rx="2"/></>,
    box: <><path d="m21 8-9-5-9 5 9 5 9-5Z"/><path d="m3 8 9 5 9-5"/><path d="M3 8v8l9 5 9-5V8"/><path d="M12 13v8"/></>,
    bag: <><path d="M6 8h12l1 13H5L6 8Z"/><path d="M9 9V6a3 3 0 0 1 6 0v3"/></>,
    users: <><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></>,
  }
  return <svg viewBox="0 0 24 24" aria-hidden="true">{paths[name]}</svg>
}

function Money({ value }) {
  return <>{new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(Number(value))}</>
}

function App() {
  const [active, setActive] = useState('overview')
  const [products, setProducts] = useState([])
  const [customers, setCustomers] = useState([])
  const [orders, setOrders] = useState([])
  const [ready, setReady] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [toast, setToast] = useState('')

  async function loadData() {
    setLoading(true)
    setError('')
    try {
      const [productData, customerData, orderData, healthData] = await Promise.all([
        api('/products'),
        api('/customers'),
        api('/orders'),
        api('/ready'),
      ])
      setProducts(productData)
      setCustomers(customerData)
      setOrders(orderData)
      setReady(healthData.status === 'ready')
    } catch (err) {
      setError(err.message)
      setReady(false)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadData() }, [])

  function notify(message) {
    setToast(message)
    window.setTimeout(() => setToast(''), 2800)
  }

  async function createProduct(event) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    try {
      await api('/products', {
        method: 'POST',
        body: JSON.stringify({
          name: form.get('name'),
          description: form.get('description') || null,
          price: form.get('price'),
          stock: Number(form.get('stock')),
          category: form.get('category'),
        }),
      })
      event.currentTarget.reset()
      notify('Product created')
      await loadData()
    } catch (err) {
      setError(err.message)
    }
  }

  async function createCustomer(event) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    try {
      await api('/customers', {
        method: 'POST',
        body: JSON.stringify({ name: form.get('name'), email: form.get('email') }),
      })
      event.currentTarget.reset()
      notify('Customer created')
      await loadData()
    } catch (err) {
      setError(err.message)
    }
  }

  async function createOrder(event) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    try {
      await api('/orders', {
        method: 'POST',
        body: JSON.stringify({
          customer_id: Number(form.get('customer')),
          items: [{ product_id: Number(form.get('product')), quantity: Number(form.get('quantity')) }],
        }),
      })
      event.currentTarget.reset()
      notify('Order placed')
      await loadData()
    } catch (err) {
      setError(err.message)
    }
  }

  const revenue = orders.reduce((sum, order) => sum + Number(order.total_amount), 0)
  const lowStock = products.filter((product) => product.stock <= 5).length

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand"><span className="brand-mark">C</span><span>Commerce</span></div>
        <nav>
          {navItems.map(([key, label]) => (
            <button key={key} className={active === key ? 'active' : ''} onClick={() => setActive(key)}>
              <Icon name={{ overview: 'grid', products: 'box', orders: 'bag', customers: 'users' }[key]} />
              {label}
            </button>
          ))}
        </nav>
        <div className="sidebar-status">
          <span className={`status-dot ${ready ? 'online' : 'offline'}`} />
          <div><strong>API status</strong><small>{ready ? 'Operational' : 'Unavailable'}</small></div>
        </div>
      </aside>

      <main>
        <header>
          <div>
            <p className="eyebrow">Workspace</p>
            <h1>{navItems.find(([key]) => key === active)?.[1]}</h1>
          </div>
          <button className="refresh" onClick={loadData}>Refresh</button>
        </header>

        {error && <div className="alert"><span>!</span>{error}<button onClick={() => setError('')}>×</button></div>}
        {toast && <div className="toast">{toast}</div>}

        {loading ? <div className="loading">Loading dashboard…</div> : (
          <>
            {active === 'overview' && (
              <>
                <section className="stats">
                  <article><span>Revenue</span><strong><Money value={revenue} /></strong><small>{orders.length} paid orders</small></article>
                  <article><span>Orders</span><strong>{orders.length}</strong><small>All-time orders</small></article>
                  <article><span>Products</span><strong>{products.length}</strong><small>{lowStock} low in stock</small></article>
                  <article><span>Customers</span><strong>{customers.length}</strong><small>Registered customers</small></article>
                </section>
                <section className="panel-grid">
                  <div className="panel">
                    <div className="panel-heading"><div><p>Inventory</p><h2>Product catalog</h2></div><button onClick={() => setActive('products')}>View all</button></div>
                    <ProductTable products={products.slice(0, 5)} />
                  </div>
                  <div className="panel">
                    <div className="panel-heading"><div><p>Latest activity</p><h2>Recent orders</h2></div><button onClick={() => setActive('orders')}>View all</button></div>
                    <OrderTable orders={orders.slice(0, 5)} />
                  </div>
                </section>
              </>
            )}

            {active === 'products' && (
              <div className="panel-grid content-grid">
                <div className="panel">
                  <div className="panel-heading"><div><p>Inventory</p><h2>All products</h2></div><span className="count">{products.length} items</span></div>
                  <ProductTable products={products} />
                </div>
                <form className="panel form-panel" onSubmit={createProduct}>
                  <div className="panel-heading"><div><p>Catalog</p><h2>Add product</h2></div></div>
                  <label>Name<input name="name" required placeholder="Product name" /></label>
                  <label>Description<textarea name="description" rows="3" placeholder="Optional description" /></label>
                  <div className="form-row">
                    <label>Price<input name="price" type="number" min="0.01" step="0.01" required placeholder="0.00" /></label>
                    <label>Stock<input name="stock" type="number" min="0" required placeholder="0" /></label>
                  </div>
                  <label>Category<input name="category" required placeholder="Electronics" /></label>
                  <button className="primary" type="submit">Create product</button>
                </form>
              </div>
            )}

            {active === 'orders' && (
              <div className="panel-grid content-grid">
                <div className="panel">
                  <div className="panel-heading"><div><p>Sales</p><h2>All orders</h2></div><span className="count">{orders.length} orders</span></div>
                  <OrderTable orders={orders} />
                </div>
                <form className="panel form-panel" onSubmit={createOrder}>
                  <div className="panel-heading"><div><p>Checkout</p><h2>Create order</h2></div></div>
                  <label>Customer<select name="customer" required><option value="">Select a customer</option>{customers.map((customer) => <option key={customer.id} value={customer.id}>{customer.name}</option>)}</select></label>
                  <label>Product<select name="product" required><option value="">Select a product</option>{products.map((product) => <option key={product.id} value={product.id}>{product.name} — <Money value={product.price} /></option>)}</select></label>
                  <label>Quantity<input name="quantity" type="number" min="1" defaultValue="1" required /></label>
                  <button className="primary" type="submit">Place order</button>
                </form>
              </div>
            )}

            {active === 'customers' && (
              <div className="panel-grid content-grid">
                <div className="panel">
                  <div className="panel-heading"><div><p>Directory</p><h2>Customers</h2></div><span className="count">{customers.length} customers</span></div>
                  <div className="table-wrap">
                    <table><thead><tr><th>ID</th><th>Name</th><th>Email</th><th>Joined</th></tr></thead>
                      <tbody>{customers.map((customer) => <tr key={customer.id}><td>#{customer.id}</td><td><strong>{customer.name}</strong></td><td>{customer.email}</td><td>{new Date(customer.created_at).toLocaleDateString()}</td></tr>)}</tbody>
                    </table>
                  </div>
                </div>
                <form className="panel form-panel" onSubmit={createCustomer}>
                  <div className="panel-heading"><div><p>Directory</p><h2>Add customer</h2></div></div>
                  <label>Name<input name="name" required placeholder="Customer name" /></label>
                  <label>Email<input name="email" type="email" required placeholder="customer@example.com" /></label>
                  <button className="primary" type="submit">Create customer</button>
                </form>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  )
}

function ProductTable({ products }) {
  return <div className="table-wrap"><table><thead><tr><th>Product</th><th>Category</th><th>Price</th><th>Stock</th></tr></thead><tbody>
    {products.map((product) => <tr key={product.id}><td><strong>{product.name}</strong><small>#{product.id}</small></td><td>{product.category}</td><td><Money value={product.price} /></td><td><span className={`stock ${product.stock <= 5 ? 'low' : ''}`}>{product.stock}</span></td></tr>)}
  </tbody></table></div>
}

function OrderTable({ orders }) {
  return <div className="table-wrap"><table><thead><tr><th>Order</th><th>Customer</th><th>Status</th><th>Total</th></tr></thead><tbody>
    {orders.map((order) => <tr key={order.id}><td><strong>#{order.id}</strong><small>{new Date(order.created_at).toLocaleDateString()}</small></td><td>Customer #{order.customer_id}</td><td><span className="status">{order.status}</span></td><td><strong><Money value={order.total_amount} /></strong></td></tr>)}
  </tbody></table></div>
}

export default App
