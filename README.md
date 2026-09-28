# Clover Order Export

**Download your full Clover order history — including itemized receipt detail — to a spreadsheet (CSV) file, for free.**

Clover's built-in dashboard export gives you payments, but **not** the individual items on each order. Clover support often points you to a paid third-party service to get itemized data. You don't need it. This is a small, free script that uses your own Clover account to pull every order, its line items, payments, refunds, and customer info into CSV files you can open in Excel, Numbers, or Google Sheets.

- ✅ **Free** — no subscriptions, no third parties. Your data goes from Clover straight to your own computer.
- ✅ **Itemized** — every line item, modifier, and discount, not just the payment total.
- ✅ **Private** — nothing is uploaded anywhere. The script talks only to Clover's official API using your own token.
- ✅ **No programming needed** — just follow the steps below.

---

## Table of contents

1. [What you get](#what-you-get)
2. [What you'll need](#what-youll-need)
3. [Step 1 — Install Python](#step-1--install-python)
4. [Step 2 — Download this tool](#step-2--download-this-tool)
5. [Step 3 — Open a terminal in the folder](#step-3--open-a-terminal-in-the-folder)
6. [Step 4 — Get your Clover API token and Merchant ID](#step-4--get-your-clover-api-token-and-merchant-id)
7. [Step 5 — Run it](#step-5--run-it)
8. [Understanding the output files](#understanding-the-output-files)
9. [All options](#all-options)
10. [Troubleshooting](#troubleshooting)
11. [Privacy & safety](#privacy--safety)
12. [License & disclaimer](#license--disclaimer)

---

## What you get

Depending on the option you choose, the script creates one or more CSV files:

| File | One row per… | Use it for |
|------|--------------|------------|
| `orders.csv` | order | A clean list of every sale: date, total, tip, tax, refund, payment type, card last-4, and customer name/email/phone. |
| `line_items.csv` | item sold | Every individual item on every order (with modifiers and discounts). Links back to `orders.csv` by the `order_id` column. |
| `report.csv` | item sold | **The "all-in-one" file** — every item with all the order and customer columns repeated on each row, so you can sort and filter everything in a single spreadsheet. |

All money is shown in dollars, and all dates/times are shown in your local time zone.

---

## What you'll need

- A computer (Windows, Mac, or Linux).
- About **10–15 minutes** the first time.
- Your **Clover login** (you'll need to be an account owner/admin to create an API token).
- That's it. You do **not** need to know how to code.

---

## Step 1 — Install Python

This tool runs on "Python," a free program that's already on many computers. First, check whether you already have it.

### Windows

1. Click the **Start** menu, type `cmd`, and press **Enter**. A black window (the "Command Prompt") opens.
2. Type this and press **Enter**:
   ```
   python --version
   ```
3. If you see something like `Python 3.11.5`, you're set — skip to Step 2.
4. If you see an error or the Microsoft Store opens, install Python:
   - Go to **https://www.python.org/downloads/** and click the big **Download Python** button.
   - Run the downloaded file. **Important:** on the first screen, check the box that says **"Add Python to PATH"**, then click **Install Now**.
   - Close and reopen the Command Prompt, and try `python --version` again.

### Mac

1. Open **Terminal** (press **Cmd + Space**, type `Terminal`, press **Enter**).
2. Type this and press **Enter**:
   ```
   python3 --version
   ```
3. If you see `Python 3.9` or higher, you're set — skip to Step 2.
4. If not, go to **https://www.python.org/downloads/**, download the macOS installer, run it, then reopen Terminal and try again.

### Linux

Most Linux systems already have Python 3. In a terminal:
```
python3 --version
```
If it's missing, install it with your package manager, e.g. on Ubuntu/Debian:
```
sudo apt install python3
```

> **Note:** This tool only uses Python's built-in features — there is **nothing else to install**, no `pip install` step.

---

## Step 2 — Download this tool

**The easy way (no Git needed):**

1. On this project's GitHub page, click the green **`< > Code`** button, then **Download ZIP**.
2. Find the downloaded ZIP in your **Downloads** folder and unzip it (double-click it on Mac; right-click → **Extract All** on Windows).
3. You now have a folder named something like `clover-order-export`. Remember where it is — you'll need it in the next step.

**If you already use Git**, you can instead run:
```
git clone https://github.com/dshafer/clover-order-export.git
```

---

## Step 3 — Open a terminal in the folder

You need to open a command window **inside** the folder you just downloaded.

### Windows

1. Open the `clover-order-export` folder in File Explorer.
2. Click in the **address bar** at the top (where the folder path is shown), type `cmd`, and press **Enter**. A Command Prompt opens already pointing at the folder.

### Mac

1. Open **Terminal**.
2. Type `cd ` (the letters c, d, and a space) — **but don't press Enter yet**.
3. Drag the `clover-order-export` folder from Finder onto the Terminal window. The folder's path appears automatically.
4. Now press **Enter**.

### Linux

Open your terminal and use `cd` to change into the folder, for example:
```
cd ~/Downloads/clover-order-export
```

To confirm you're in the right place, type `ls` (Mac/Linux) or `dir` (Windows) and press Enter — you should see `clover_export.py` listed.

---

## Step 4 — Get your Clover API token and Merchant ID

You need two things from Clover: an **API token** (a long password that lets the script read your data) and your **Merchant ID**.

### Get your API token

1. Log in to your Clover Dashboard at **https://www.clover.com/dashboard**.
2. First-time requirement: Clover requires **two-factor authentication** to be turned on before you can create a token. If prompted, set it up (Account & Setup → Security).
3. Click the **Settings gear** → **View all settings**.
4. Under **Business Operations**, click **API tokens**.
5. Click **Get Started** (or **Create Token**).
6. When choosing permissions, grant **read** access to at least: **Orders, Payments, Customers, Inventory**. (Read-only is all this tool needs — it never changes anything.)
7. Click **Create Token** and **copy the token string**. Keep it somewhere safe and private — treat it like a password.

### Find your Merchant ID

- It's the ~13-character code in your dashboard web address. When you're logged in, the URL looks like:
  `https://www.clover.com/dashboard/m/**XXXXXXXXXXXXX**/...`
  The bold part is your Merchant ID.
- It's also shown under **Account & Setup → About Your Business**.

> **Using Clover outside North America?** Your data may live on a regional server. See the `--region` option below.

---

## Step 5 — Run it

In the terminal window from Step 3, type the command for your system and press **Enter**.

- **Windows:** use `python`
- **Mac/Linux:** use `python3`

**The simplest way** — just run it and answer the questions it asks (it will prompt you for your token, Merchant ID, and dates):

```
python3 clover_export.py
```

When it asks for your token, paste it in (on Mac/Linux the token stays hidden as you type — that's normal) and press Enter.

**Or give it the dates up front:**

```
python3 clover_export.py --start 2025-01-01 --end 2025-12-31
```

**To get the single all-in-one spreadsheet** (`report.csv`):

```
python3 clover_export.py --start 2025-01-01 --end 2025-12-31 --format single
```

When it finishes, it prints the location of the CSV file(s) it created — by default in a new folder named `clover_export_<date_time>` next to the script. Open that file in Excel, Numbers, or Google Sheets.

> Dates are written **year-month-day**: `2025-01-31` means January 31, 2025. Both the start and end dates are included. You can request any range you like — the tool automatically handles Clover's 90-day-per-request limit behind the scenes.

---

## Understanding the output files

**`orders.csv`** and **`report.csv`** share these order-level columns:

| Column | Meaning |
|--------|---------|
| `order_id` | Clover's unique ID for the order |
| `created_local` / `modified_local` | When the order was created / last changed (your local time) |
| `state` | Order status (e.g. paid, open) |
| `order_type` | e.g. "Sale," "Refund" |
| `order_total` | Order total, in dollars |
| `amount_paid`, `tip`, `tax_paid` | Payment amounts, in dollars |
| `refund_total` | Total refunded on the order |
| `payment_count`, `tenders`, `card_types`, `card_last4` | How it was paid |
| `customer_name`, `customer_email`, `customer_phone` | The customer (blank for anonymous/walk-in orders) |
| `employee` | Who rang it up |
| `note` | The order note |
| `line_item_count` | How many items were on the order |

**`line_items.csv`** and the `item_…` columns in **`report.csv`** describe each item:

| Column | Meaning |
|--------|---------|
| `item_name` (or `name`) | The item sold |
| `item_price` (or `price`) | Item price, in dollars |
| `item_qty_unitQty` | Quantity for weighed/measured items |
| `item_modifications` | Add-ons/modifiers (e.g. "Extra shot (+0.75)") |
| `item_line_discounts` | Discounts applied to that item |
| `item_refunded`, `item_exchanged` | Whether the item was refunded/exchanged |

To combine `orders.csv` and `line_items.csv` yourself, match rows where the `order_id` is the same. (Or just use `report.csv`, which already has everything on one row.)

---

## All options

| Option | What it does | Default |
|--------|--------------|---------|
| `--start YYYY-MM-DD` | First day to include | asks you if omitted |
| `--end YYYY-MM-DD` | Last day to include | asks you if omitted |
| `--format split\|single\|both` | `split` = `orders.csv` + `line_items.csv`; `single` = one `report.csv`; `both` = all three | `split` |
| `--outdir FOLDER` | Where to save the files | a new timestamped folder |
| `--region us\|eu\|la` | Clover server region (US, Europe, Latin America) | `us` |
| `--tz TIMEZONE` | Time zone for dates, e.g. `America/New_York` | `America/Chicago` |

To see this list any time, run:
```
python3 clover_export.py --help
```

**Repeat users:** instead of typing your token each time, you can save your credentials as "environment variables" so the script picks them up automatically. On Mac/Linux:
```
export CLOVER_API_TOKEN="your-token-here"
export CLOVER_MERCHANT_ID="your-merchant-id"
```

---

## Troubleshooting

**"python is not recognized" / "command not found"**
Python isn't installed or wasn't added to PATH. Redo [Step 1](#step-1--install-python). On Windows, make sure you checked **"Add Python to PATH"** during install. Try `python3` instead of `python` (or vice versa).

**`ERROR 401 Unauthorized`**
Your API token is wrong, expired, or missing permissions. Recreate it (see [Step 4](#step-4--get-your-clover-api-token-and-merchant-id)) and make sure **Orders, Payments, Customers, Inventory** read access is granted.

**`ERROR 404 Not Found`**
Your Merchant ID is wrong, or your account is on a different regional server. Double-check the Merchant ID, and if you're outside North America try adding `--region eu` or `--region la`.

**Names, emails, or phone numbers are blank**
That customer is either an anonymous walk-in (no customer attached to the order) or has no name saved in Clover. The tool shows whatever Clover has.

**It's slow or seems stuck**
Large date ranges with thousands of orders take time. The tool prints its progress; let it finish. It also automatically slows down and retries if Clover asks it to.

**Python 3.9+ required**
This tool needs Python version 3.9 or newer. Check with `python3 --version` and update from https://www.python.org/downloads/ if needed.

---

## Privacy & safety

- **Your data stays on your computer.** The script contacts only Clover's official API (`api.clover.com`). It does not send your data or your token anywhere else.
- **Protect your API token** like a password. Anyone with it can read your business data. If it's ever exposed, delete it in the Clover Dashboard and create a new one.
- **The exported CSVs contain customer information** (names, emails, phone numbers). Store them securely and don't post them publicly. If you use Git, note that this project's `.gitignore` is set up to help prevent accidentally committing exported CSV files.

---

## License & disclaimer

Released under the [MIT License](LICENSE) — free to use, modify, and share.

This is an independent, unofficial tool. It is **not affiliated with, endorsed by, or supported by Clover Network, Inc.** "Clover" is a trademark of its respective owner. Use at your own risk; always verify exported figures against your official Clover reports before relying on them for accounting or tax purposes.
