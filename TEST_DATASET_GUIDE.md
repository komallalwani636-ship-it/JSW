# Comprehensive Test Dataset: `TEST_CPL2_COMPREHENSIVE_DATASET.xlsx`

This test dataset has been engineered to test **every single business rule, filter condition, edge case, and violation pattern** in the CPL-2 Scheduling System.

---

## 📊 Summary Overview

| Metric | Expected Value | Description |
| :--- | :--- | :--- |
| **Total Rows Read** | `98` | Full coil inventory entries |
| **Parse Warnings** | `10` | Non-numeric routing strings (`TTSJ`, `SPCL`, `W`, `TTJ`, `CPL2`, `WT`) |
| **Eligible Coils** | `74` | Ready for CPL-2 sequencing |
| **APL7 Tracked Coils** | `6` | Coils with `Receiving Remarks = APL7` |
| **Excluded — Product** | `3` | Non-CPL-2 products (`CR`, `GP`, `GI`) |
| **Excluded — Act Path / Prev Unit** | `8` | In-progress routing paths or non-zero units |
| **Excluded — Status** | `4` | Non-eligible inventory statuses (`HOLD`, `REJ`, `BLOCKED`, `SCRAP`) |
| **Excluded — Closed Orders** | `3` | Closed customer sales orders (`CLOSED`) |
| **Excluded — Age** | `4` | Fresh inventory with aging $\le 72\,\text{hours}$ (24h, 48h, 72h) |
| **Raw Violations** | `13` | Width jumps (4), Thickness steps (1), TDC adjacencies (8) |
| **After Auto-Optimization** | `0` | All violations automatically eliminated |

---

## 🧪 Detailed Patterns & Test Scenarios

### 1. Eligible Campaign Products
* **HRPO Coils (28 coils)**: Standard hot-rolled pickled & oiled coils with varied thicknesses ($1.6\,\text{mm}$ to $4.0\,\text{mm}$) and widths ($1200\,\text{mm}$ to $1250\,\text{mm}$).
* **HRSPO Coils (12 coils)**: Skinpassed coils across 3 aging milestones:
  * Age $> 72\,\text{h}$
  * Age $> 120\,\text{h}$
  * Age $> 168\,\text{h}$ (7-day FIFO high priority aging)
* **NGO FP Coils (12 coils)**: Non-Grain Oriented electrical steel across 4 silicon content bands:
  * **Ultra-Low Silicon** ($< 0.1\%$): $\text{Si} = 0.04\%$
  * **Low Silicon** ($0.1\% - 0.5\%$): $\text{Si} = 0.25\%$
  * **Medium Silicon** ($0.5\% - 1.5\%$): $\text{Si} = 0.85\%$
  * **High Silicon** ($> 1.5\%$): $\text{Si} = 2.10\%$

### 2. APL7 Tracked Coils (6 coils)
* Coils marked with `Receiving Remarks = APL7` and `Next Work Center = APL7`.
* Filtered out of main CPL-2 line sequencing and placed in the dedicated **APL7 Tracked Section**.

### 3. Exclusions & Edge Cases
* **Non-CPL-2 Products**: Coils with `Product = CR`, `GP`, `GI` $\to$ Excluded at Step 1.
* **Routing Path Exclusions**:
  * String routing codes: `Act Path = TTSJ`, `W`, `TTJ`, `T`, `WT` with `Prev Unit = SPCL` or `CPL2` $\to$ Generates parse warnings and excluded at Step 2.
  * Non-zero numeric units: `(1, 0)`, `(0, 2)`, `(3, 4)` $\to$ Excluded at Step 2.
* **Status Exclusions**: Coils with `Status = HOLD`, `REJ`, `BLOCKED`, `SCRAP` $\to$ Excluded at Step 3 (`Status != TA/TW`).
* **Closed Orders**: Coils with `Order_status = CLOSED` $\to$ Excluded at Step 4.
* **Under-Aged Coils**: Coils with `Age Hours = 12h, 24h, 48h, 72h` $\to$ Excluded at Age Step ($\le 72\text{h}$).

### 4. Violation Injection Triggers
* **Width Jump (Thin, $< 2.0\,\text{mm}$)**:
  * `VIOL_WDT_THIN_A` ($1260\,\text{mm}$) adjacent to `VIOL_WDT_THIN_B` ($1020\,\text{mm}$) $\to$ Step change of $240\,\text{mm} \ge 150\,\text{mm}$ maximum allowed limit.
* **Width Jump (Thick, $\ge 2.0\,\text{mm}$)**:
  * `VIOL_WDT_THICK_A` ($1550\,\text{mm}$) adjacent to `VIOL_WDT_THICK_B` ($1100\,\text{mm}$) $\to$ Step change of $450\,\text{mm} \ge 300\,\text{mm}$ maximum allowed limit.
* **Thickness Step (Thin, $< 2.0\,\text{mm}$)**:
  * `VIOL_THK_THIN_A` ($1.5\,\text{mm}$) adjacent to `VIOL_THK_THIN_B` ($1.95\,\text{mm}$) $\to$ Step change of $0.45\,\text{mm} > 0.4\,\text{mm}$ maximum allowed limit.
* **Thickness Step (Thick, $\ge 2.0\,\text{mm}$)**:
  * `VIOL_THK_THICK_A` ($2.5\,\text{mm}$) adjacent to `VIOL_THK_THICK_B` ($4.2\,\text{mm}$) $\to$ Step change of $1.7\,\text{mm} > 1.0\,\text{mm}$ maximum allowed limit.
* **Critical TDC Grade Adjacency**:
  * 10 coils carrying critical grades: `JVPFB60AJS`, `JVPTR14AJS`, `JVPST01C00`, `JVPTR15AJS`, `JVPTR13AJS` adjacent to each other to test TDC separation and swap resolution.

---

## 🚀 How to Test It in the Web Application

1. Open the application dashboard: `http://localhost:5173/`.
2. In the **Upload HR Stock Report** section:
   * Select or drag-and-drop the generated file: `TEST_CPL2_COMPREHENSIVE_DATASET.xlsx` (located in the project root folder).
   * Click **Upload**.
3. Observe the **Parse & Exclusion Summary**:
   * Total rows: `98`
   * Eligible coils: `74`
   * APL7 coils: `6`
   * Exclusions broken down by Product (3), Act Path (8), Status (4), Closed Orders (3).
   * Parse warnings displaying the 10 non-numeric routing codes.
4. Click **Generate Schedule**:
   * Inspect the schedule with full violation detection and the **⚡ Auto-Resolve Violations** optimizer.
