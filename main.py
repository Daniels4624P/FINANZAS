from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import pandas as pd
import sqlalchemy
import io

app = FastAPI()

# Configuración de CORS para permitir peticiones desde Express
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://api-familia-tareas-node.onrender.com"],  # Cambia esto a la URL de tu API de Express en producción
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)

# Conexión a la base de datos
DATABASE_URL = "postgresql://neondb_owner:npg_W1qfEuBdANj4@ep-square-block-a8x6hhxv-pooler.eastus2.azure.neon.tech/neondb?sslmode=require"
engine = sqlalchemy.create_engine(DATABASE_URL)

@app.get("/export/finances")
def exportar_finanzas(year: int = Query(None), month: int = Query(None)):
    """Genera un CSV con los gastos, ingresos y análisis financiero."""
    try:
        # Construir la consulta SQL para gastos
        expenses_query = 'SELECT fecha, valor, description FROM "expenses"'
        incomes_query = 'SELECT fecha, valor, description FROM "incomes"'

        filters = []
        if year:
            filters.append(f"EXTRACT(YEAR FROM fecha) = {year}")
        if month:
            filters.append(f"EXTRACT(MONTH FROM fecha) = {month}")

        if filters:
            expenses_query += " WHERE " + " AND ".join(filters)
            incomes_query += " WHERE " + " AND ".join(filters)

        # Cargar datos de la base de datos
        expenses_df = pd.read_sql(expenses_query, con=engine)
        incomes_df = pd.read_sql(incomes_query, con=engine)

        # Cálculos financieros
        total_expenses = expenses_df["valor"].sum() if not expenses_df.empty else 0
        total_incomes = incomes_df["valor"].sum() if not incomes_df.empty else 0
        balance = total_incomes - total_expenses
        gasto_promedio_mensual = total_expenses / month if month and month > 0 else total_expenses / 12
        porcentaje_gastado = (total_expenses / total_incomes * 100) if total_incomes > 0 else 0

        # Crear DataFrame de análisis financiero
        analysis_data = {
            "Métrica": ["Total Ingresos", "Total Gastos", "Balance", "Gasto Promedio Mensual", "Porcentaje de Ingresos Gastados"],
            "Valor": [total_incomes, total_expenses, balance, gasto_promedio_mensual, f"{porcentaje_gastado:.2f}%"]
        }
        analysis_df = pd.DataFrame(analysis_data)

        # Combinar todo en un solo archivo CSV
        output = io.StringIO()
        output.write("### Análisis Financiero\n")
        analysis_df.to_csv(output, index=False, encoding="utf-8")
        output.write("\n### Ingresos\n")
        incomes_df.to_csv(output, index=False, encoding="utf-8")
        output.write("\n### Gastos\n")
        expenses_df.to_csv(output, index=False, encoding="utf-8")
        output.seek(0)

        return StreamingResponse(
            output,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=finanzas.csv"}
        )
    
    except Exception as e:
        return {"error": str(e)}
