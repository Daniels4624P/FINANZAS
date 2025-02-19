from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import pandas as pd
import sqlalchemy
import io

app = FastAPI()

# Configuración de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://api-familia-tareas-node.onrender.com"],  
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)

# Conexión a la base de datos
DATABASE_URL = "postgresql://neondb_owner:npg_W1qfEuBdANj4@ep-square-block-a8x6hhxv-pooler.eastus2.azure.neon.tech/neondb?sslmode=require"
engine = sqlalchemy.create_engine(DATABASE_URL)

@app.get("/export/public-transactions")
def export_public_transactions(year: int = Query(...), month: int = Query(...)):
    """Genera un CSV con el análisis financiero de TODAS las transacciones públicas"""
    try:
        expenses_query = f"""
            SELECT e.fecha, e.valor, e.description, c.name AS categoria, 
                   a1.name AS cuenta_origen, a2.name AS cuenta_destino, u.name AS usuario
            FROM "Expenses" e
            LEFT JOIN "Categories" c ON e.categoria_id = c.id
            LEFT JOIN "Accounts" a1 ON e.cuenta_id = a1.id
            LEFT JOIN "Accounts" a2 ON e.destino_id = a2.id
            LEFT JOIN "Users" u ON e.user_id = u.id
            WHERE a1.public = TRUE
            AND EXTRACT(YEAR FROM e.fecha) = {year} AND EXTRACT(MONTH FROM e.fecha) = {month}
        """

        incomes_query = f"""
            SELECT i.fecha, i.valor, i.description, c.name AS categoria, 
                   a.name AS cuenta, u.name AS usuario
            FROM "Incomes" i
            LEFT JOIN "Categories" c ON i.categoria_id = c.id
            LEFT JOIN "Accounts" a ON i.cuenta_id = a.id
            LEFT JOIN "Users" u ON i.user_id = u.id
            WHERE a.public = TRUE
            AND EXTRACT(YEAR FROM i.fecha) = {year} AND EXTRACT(MONTH FROM i.fecha) = {month}
        """

        expenses_df = pd.read_sql(expenses_query, con=engine)
        incomes_df = pd.read_sql(incomes_query, con=engine)

        # Cálculos financieros
        total_expenses = expenses_df["valor"].sum() if not expenses_df.empty else 0
        total_incomes = incomes_df["valor"].sum() if not incomes_df.empty else 0
        balance = total_incomes - total_expenses
        porcentaje_gastado = (total_expenses / total_incomes * 100) if total_incomes > 0 else 0

        gastos_fijos = expenses_df[expenses_df["categoria"].isin(["Renta", "Servicios", "Educación"])]
        total_gastos_fijos = gastos_fijos["valor"].sum() if not gastos_fijos.empty else 0
        gastos_variables = total_expenses - total_gastos_fijos
        porcentaje_gastos_variables = (gastos_variables / total_expenses * 100) if total_expenses > 0 else 0
        proyeccion_3_meses = balance * 3
        proyeccion_6_meses = balance * 6

        # Análisis Financiero
        analysis_data = {
            "Métrica": ["Total Ingresos", "Total Gastos", "Balance", "Porcentaje de Ingresos Gastados", 
                        "Gastos Fijos", "Gastos Variables", "% Gastos Variables", 
                        "Proyección a 3 meses", "Proyección a 6 meses"],
            "Valor": [f"${total_incomes:,.2f}", f"${total_expenses:,.2f}", f"${balance:,.2f}", 
                      f"{porcentaje_gastado:.2f}%", f"${total_gastos_fijos:,.2f}", f"${gastos_variables:,.2f}", 
                      f"{porcentaje_gastos_variables:.2f}%", f"${proyeccion_3_meses:,.2f}", f"${proyeccion_6_meses:,.2f}"]
        }
        analysis_df = pd.DataFrame(analysis_data)

        # Porcentaje de Gasto por Categoría
        category_spending = expenses_df.groupby("categoria")["valor"].sum().reset_index()
        category_spending["% del Gasto"] = (category_spending["valor"] / total_expenses * 100).round(2).astype(str) + "%"

        # Crear CSV
        output = io.StringIO()
        output.write("### 📊 Análisis de TODAS las Transacciones Públicas ###\n")
        analysis_df.to_csv(output, index=False, encoding="utf-8")
        output.write("\n### 📊 Porcentaje de Gasto por Categoría ###\n")
        category_spending.to_csv(output, index=False, encoding="utf-8")
        output.write("\n### 💸 Gastos Públicos ###\n")
        expenses_df.to_csv(output, index=False, encoding="utf-8")
        output.write("\n### 💰 Ingresos Públicos ###\n")
        incomes_df.to_csv(output, index=False, encoding="utf-8")
        output.seek(0)

        return StreamingResponse(output, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=public_transactions.csv"})
    
    except Exception as e:
        return {"error": str(e)}

@app.get("/export/private-transactions")
def export_private_transactions(year: int = Query(...), month: int = Query(...), user_id: int = Query(...)):
    """Genera un CSV con el análisis financiero de cuentas privadas del usuario autenticado"""
    try:
        query = f"""
        SELECT a.name AS cuenta, COALESCE(SUM(i.valor), 0) AS total_ingresos,
               COALESCE(SUM(e.valor), 0) AS total_gastos, 
               COALESCE(SUM(i.valor), 0) - COALESCE(SUM(e.valor), 0) AS balance
        FROM Accounts a
        LEFT JOIN Expenses e ON a.id = e.cuenta_id
        LEFT JOIN Incomes i ON a.id = i.cuenta_id
        WHERE a.user_id = {user_id} AND a.public = FALSE
        AND EXTRACT(YEAR FROM e.fecha) = {year} AND EXTRACT(MONTH FROM e.fecha) = {month}
        GROUP BY a.name
        """

        df = pd.read_sql(query, con=engine)

        if df.empty:
            raise HTTPException(status_code=404, detail="No hay transacciones privadas registradas")

        output = io.StringIO()
        df.to_csv(output, index=False, encoding="utf-8")
        output.seek(0)

        return StreamingResponse(output, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=private_transactions.csv"})
    
    except Exception as e:
        return {"error": str(e)}
