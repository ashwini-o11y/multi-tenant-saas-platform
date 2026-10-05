const API_BASE_URL = "http://127.0.0.1:8000";

const tenantSelect = document.querySelector("#tenant-select");
const errorMessage = document.querySelector("#error-message");
const tenantName = document.querySelector("#tenant-name");
const tenantId = document.querySelector("#tenant-id");
const customerRows = document.querySelector("#customer-rows");
const transactionRows = document.querySelector("#transaction-rows");
const customerCount = document.querySelector("#customer-count");
const transactionCount = document.querySelector("#transaction-count");
let activeRequest = null;

async function getTenantData(path, selectedTenant, signal) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { "X-Tenant-ID": selectedTenant },
    signal,
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed with status ${response.status}`);
  }

  return response.json();
}

function showMessage(message) {
  errorMessage.textContent = message;
  errorMessage.hidden = !message;
}

function renderCustomers(customers) {
  customerRows.replaceChildren();
  customerCount.textContent = String(customers.length);

  for (const customer of customers) {
    const row = document.createElement("tr");
    const name = document.createElement("td");
    const email = document.createElement("td");
    name.textContent = customer.name;
    email.textContent = customer.email;
    email.className = "muted-cell";
    row.append(name, email);
    customerRows.append(row);
  }

  if (customers.length === 0) {
    customerRows.innerHTML = '<tr><td class="empty-state" colspan="2">No customers found.</td></tr>';
  }
}

function renderTransactions(transactions) {
  transactionRows.replaceChildren();
  transactionCount.textContent = String(transactions.length);

  for (const transaction of transactions) {
    const row = document.createElement("tr");
    const description = document.createElement("td");
    const date = document.createElement("td");
    const amount = document.createElement("td");
    const value = Number(transaction.amount);

    description.textContent = transaction.description;
    date.textContent = new Date(transaction.created_at).toLocaleDateString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
    amount.textContent = new Intl.NumberFormat(undefined, {
      style: "currency",
      currency: transaction.currency,
    }).format(value);
    amount.className = value < 0 ? "amount amount-debit" : "amount";
    row.append(description, date, amount);
    transactionRows.append(row);
  }

  if (transactions.length === 0) {
    transactionRows.innerHTML = '<tr><td class="empty-state" colspan="3">No transactions found.</td></tr>';
  }
}

async function loadTenantWorkspace() {
  activeRequest?.abort();
  activeRequest = new AbortController();
  const { signal } = activeRequest;
  const selectedTenant = tenantSelect.value;
  showMessage("");
  tenantName.textContent = "Loading...";
  tenantId.textContent = selectedTenant;
  customerRows.innerHTML = '<tr><td class="empty-state" colspan="2">Loading customers...</td></tr>';
  transactionRows.innerHTML = '<tr><td class="empty-state" colspan="3">Loading transactions...</td></tr>';
  customerCount.textContent = "--";
  transactionCount.textContent = "--";

  try {
    const [tenant, customers, transactions] = await Promise.all([
      getTenantData("/api/v1/tenant", selectedTenant, signal),
      getTenantData("/api/v1/customers", selectedTenant, signal),
      getTenantData("/api/v1/transactions", selectedTenant, signal),
    ]);
    if (signal.aborted) return;
    tenantName.textContent = tenant.name;
    tenantId.textContent = tenant.id;
    renderCustomers(customers);
    renderTransactions(transactions);
  } catch (error) {
    if (error.name === "AbortError") return;
    tenantName.textContent = "Unavailable";
    customerRows.innerHTML = '<tr><td class="empty-state" colspan="2">Data unavailable.</td></tr>';
    transactionRows.innerHTML = '<tr><td class="empty-state" colspan="3">Data unavailable.</td></tr>';
    customerCount.textContent = "--";
    transactionCount.textContent = "--";
    showMessage(`Could not load tenant data: ${error.message}. Confirm that the API is running.`);
  }
}

tenantSelect.addEventListener("change", loadTenantWorkspace);
loadTenantWorkspace();