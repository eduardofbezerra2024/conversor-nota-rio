import streamlit as st
import xml.etree.ElementTree as ET
from xml.dom import minidom
import re
import io

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Conversor NFS-e Nacional", page_icon="📄")

st.title("📄 Conversor: Nota Carioca → Padrão Nacional")
st.markdown("""
Esta ferramenta converte o arquivo **TXT antigo (Prefeitura do Rio)** para o novo formato **XML (Padrão Nacional ADN)**.
""")

# --- BARRA LATERAL (CONFIGURAÇÕES) ---
st.sidebar.header("Dados do Prestador")
cnpj_prestador = st.sidebar.text_input("Seu CNPJ (apenas números)", value="00000000000000")
inscricao_municipal = st.sidebar.text_input("Inscrição Municipal", value="000000")
st.sidebar.info("Preencha estes dados para o XML ser validado corretamente.")

# --- FUNÇÕES DE AJUDA ---
def formatar_valor(valor_str):
    if not valor_str: return "0.00"
    try:
        valor = float(valor_str) / 100
        return "{:.2f}".format(valor)
    except:
        return "0.00"

def formatar_data(data_str):
    if len(data_str) != 8: return data_str
    return f"{data_str[0:4]}-{data_str[4:6]}-{data_str[6:8]}"

# --- LÓGICA DE CONVERSÃO ---
def converter_arquivo(conteudo_arquivo):
    notas = []
    
    # Regex para capturar os blocos que começam com 200
    padrao_rps = re.compile(r'(200\s+\d+.*?)(?=200\s+\d|900\d|$)', re.DOTALL)
    matches = padrao_rps.findall(conteudo_arquivo)
    
    for bloco in matches:
        linha_limpa = bloco.replace('\n', '').replace('\r', '')
        
        # Extração via Regex
        match_rps = re.search(r'200\s+0+(\d+)', linha_limpa)
        num_rps = match_rps.group(1) if match_rps else "0"
        
        match_data = re.search(r'(20\d{6})', linha_limpa)
        data_emissao = match_data.group(1) if match_data else "20260101"

        match_valor = re.findall(r'000(\d{3,15})', linha_limpa)
        valor_servico = match_valor[-2] if len(match_valor) > 1 else "0"

        partes = linha_limpa.split('Serviços prestados')
        desc = "Serviços prestados" + partes[1] if len(partes) > 1 else "Serviços de Agenciamento"
        desc = desc.split("NÃO GERA COBRANÇA")[0]

        idx_data = linha_limpa.find(data_emissao)
        tomador_doc = linha_limpa[idx_data+9 : idx_data+25].strip()
        if len(tomador_doc) > 14: tomador_doc = tomador_doc[1:]

        notas.append({
            'numero': num_rps,
            'data': data_emissao,
            'valor': valor_servico,
            'codigo_servico': "0902",
            'discriminacao': desc.strip(),
            'tomador_doc': tomador_doc
        })
    
    return notas

def gerar_xml(lista_notas):
    lote = ET.Element('EnviarLoteRpsEnvio', xmlns="http://www.abrasf.org.br/nfse.xsd")
    lote_rps = ET.SubElement(lote, 'LoteRps')
    
    ET.SubElement(lote_rps, 'NumeroLote').text = "1"
    ET.SubElement(lote_rps, 'Cnpj').text = cnpj_prestador
    ET.SubElement(lote_rps, 'InscricaoMunicipal').text = inscricao_municipal
    
    lista_rps_elem = ET.SubElement(lote_rps, 'ListaRps')

    for nota in lista_notas:
        rps = ET.SubElement(lista_rps_elem, 'Rps')
        inf_rps = ET.SubElement(rps, 'InfDeclaracaoPrestacaoServico')
        
        rps_id = ET.SubElement(inf_rps, 'Rps')
        id_rps = ET.SubElement(rps_id, 'IdentificacaoRps')
        ET.SubElement(id_rps, 'Numero').text = nota['numero']
        ET.SubElement(id_rps, 'Serie').text = "1"
        ET.SubElement(id_rps, 'Tipo').text = "1"
        
        ET.SubElement(inf_rps, 'DataEmissao').text = formatar_data(nota['data'])
        ET.SubElement(inf_rps, 'Status').text = "1"

        servico = ET.SubElement(inf_rps, 'Servico')
        valores = ET.SubElement(servico, 'Valores')
        ET.SubElement(valores, 'ValorServicos').text = formatar_valor(nota['valor'])
        
        codigo_formatado = f"{nota['codigo_servico'][:2]}.{nota['codigo_servico'][2:]}"
        ET.SubElement(servico, 'ItemListaServico').text = codigo_formatado
        ET.SubElement(servico, 'Discriminacao').text = nota['discriminacao']
        ET.SubElement(servico, 'CodigoMunicipio').text = "3304557"

        prestador = ET.SubElement(inf_rps, 'Prestador')
        ET.SubElement(prestador, 'Cnpj').text = cnpj_prestador
        ET.SubElement(prestador, 'InscricaoMunicipal').text = inscricao_municipal

        tomador = ET.SubElement(inf_rps, 'Tomador')
        ident_tomador = ET.SubElement(tomador, 'IdentificacaoTomador')
        cpf_cnpj = ET.SubElement(ident_tomador, 'CpfCnpj')
        
        doc_limpo = nota['tomador_doc'].strip()
        if len(doc_limpo) > 11:
            ET.SubElement(cpf_cnpj, 'Cnpj').text = doc_limpo
        else:
            ET.SubElement(cpf_cnpj, 'Cpf').text = doc_limpo

    # Retorna o XML como string bytes para download
    xml_str = minidom.parseString(ET.tostring(lote)).toprettyxml(indent="   ")
    return xml_str.encode('utf-8')

# --- INTERFACE PRINCIPAL ---
uploaded_file = st.file_uploader("Solte seu arquivo TXT aqui", type=['txt'])

if uploaded_file is not None:
    # Ler arquivo da memória
    string_data = uploaded_file.getvalue().decode("latin-1")
    
    if st.button("Converter Agora"):
        with st.spinner('Processando notas...'):
            try:
                notas_processadas = converter_arquivo(string_data)
                
                if not notas_processadas:
                    st.error("Nenhuma nota encontrada. Verifique se o arquivo está no formato correto.")
                else:
                    st.success(f"Sucesso! {len(notas_processadas)} notas encontradas.")
                    
                    # Gera o XML
                    xml_bytes = gerar_xml(notas_processadas)
                    
                    # Botão de Download
                    st.download_button(
                        label="⬇️ Baixar XML Convertido",
                        data=xml_bytes,
                        file_name="lote_nacional_convertido.xml",
                        mime="application/xml"
                    )
                    
                    # Preview dos dados
                    with st.expander("Ver dados extraídos (Conferência)"):
                        st.write(notas_processadas)
                        
            except Exception as e:
                st.error(f"Erro ao converter: {e}")