from .transformer_models import TPXTransformer

def run_simulation(ui_data):
    # 1. Instanciar o transformador
    tpx_model = TPXTransformer(ui_data)

    # 2. Fazer os cálculos de tensão
    vsat = tpx_model.calculate_saturation_voltage()
    v_req_perm, v_req_trans = tpx_model.calculate_required_voltages()

    # 3. Lógica de Saturação (baseada em tensão)
    saturates_perm = vsat < v_req_perm
    saturates_trans = vsat < v_req_trans

    # 4. Calcular tempo para saturação se aplicável
    tsat = tpx_model.calculate_saturation_time(v_req_trans) if saturates_trans else float('inf')

    # 5. Simular as formas de onda para o gráfico
    waveforms = tpx_model.simulate_current_waveforms()

    # 6. Retornar todos os resultados para a UI
    results = {
        "vsat": vsat,
        "v_req_perm": v_req_perm,
        # ... outros resultados
        "waveforms": waveforms
    }
    return results