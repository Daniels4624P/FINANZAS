from fastapi import FastAPI, Query
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

@app.get("/export/finances")
def exportar_finanzas(year: int = Query(None), month: int = Query(None)):
    """Genera un CSV con los gastos, ingresos y análisis financiero en un formato ordenado."""
    try:
        # Consultas SQL
        expenses_query = f"""
            SELECT e.fecha, e.valor, e.description, c.name AS categoria, a.name AS cuenta
            FROM "Expenses" e
            LEFT JOIN "Categories" c ON e.categoria_id = c.id
            LEFT JOIN "Accounts" a ON e.cuenta_id = a.id
            WHERE EXTRACT(YEAR FROM e.fecha) = {year} AND EXTRACT(MONTH FROM e.fecha) = {month}
        """

        incomes_query = f"""
            SELECT i.fecha, i.valor, i.description, c.name AS categoria, a.name AS cuenta
            FROM "Incomes" i
            LEFT JOIN "Categories" c ON i.categoria_id = c.id
            LEFT JOIN "Accounts" a ON i.cuenta_id = a.id
            WHERE EXTRACT(YEAR FROM i.fecha) = {year} AND EXTRACT(MONTH FROM i.fecha) = {month}
        """

        # Cargar datos
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
            "Métrica": ["Total Ingresos", "Total Gastos", "Balance", "Porcentaje de Ingresos Gastados", "Gastos Fijos", "Gastos Variables", "% Gastos Variables", "Proyección a 3 meses", "Proyección a 6 meses"],
            "Valor": [f"${total_incomes:,.2f}", f"${total_expenses:,.2f}", f"${balance:,.2f}", f"{porcentaje_gastado:.2f}%", f"${total_gastos_fijos:,.2f}", f"${gastos_variables:,.2f}", f"{porcentaje_gastos_variables:.2f}%", f"${proyeccion_3_meses:,.2f}", f"${proyeccion_6_meses:,.2f}"]
        }
        analysis_df = pd.DataFrame(analysis_data)

        # Porcentaje de Gasto por Categoría
        category_spending = expenses_df.groupby("categoria")["valor"].sum().reset_index()
        category_spending["% del Gasto"] = (category_spending["valor"] / total_expenses * 100).round(2).astype(str) + "%"
        
        # Formato monetario
        expenses_df["valor"] = expenses_df["valor"].apply(lambda x: f"${x:,.2f}")
        incomes_df["valor"] = incomes_df["valor"].apply(lambda x: f"${x:,.2f}")
        category_spending["valor"] = category_spending["valor"].apply(lambda x: f"${x:,.2f}")
        
        # Crear CSV
        output = io.StringIO()
        output.write("###############################################\n")
        output.write("### 🏦 ANÁLISIS FINANCIERO FAMILIAR 📊 ###\n")
        output.write("###############################################\n\n")
        output.write("### 📈 Análisis Financiero ###\n")
        analysis_df.to_csv(output, index=False, encoding="utf-8")
        output.write("\n### 📊 Porcentaje de Gasto por Categoría ###\n")
        category_spending.to_csv(output, index=False, encoding="utf-8")
        output.write("\n### 💰 Ingresos ###\n")
        incomes_df.to_csv(output, index=False, encoding="utf-8")
        output.write("\n### 💸 Gastos ###\n")
        expenses_df.to_csv(output, index=False, encoding="utf-8")
        output.seek(0)

        return StreamingResponse(
            output,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=finanzas_familia.csv"}
        )
    
    except Exception as e:
        return {"error": str(e)}
