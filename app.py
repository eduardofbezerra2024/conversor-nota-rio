import streamlit as st
import xml.etree.ElementTree as ET
from xml.dom import minidom
import re

# --- CONFIGURAÇÃO VISUAL ---
st.set_page_config(layout="wide", page_title="Conversor Oficial", page_icon="🏢")

# Esconde menu hambúrguer e rodapé do Streamlit para ficar profissional
hide_streamlit_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            .block-container {padding-top: 2rem; padding-bottom: 2rem;}
            input {border-radius: 5px;}
            </style>
            """
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# --- TÍTULO INTERNO ---
st.markdown("### ⚙️ Dados da Empresa Prestadora")
st.info("Preencha abaixo os dados de quem está emitindo a nota (Sua Empresa) para validar o arquivo.")

# --- FORMULÁRIO NO TOPO (MUDANÇA PRINCIPAL) ---
# Em vez de sidebar, usamos colunas no centro
col1, col2 = st.columns(2)

with col1:
    cnpj_prestador = st.text_input("CNPJ do Prestador (Só números)", placeholder="Ex: 00000000000191")

with col2:
    inscricao_municipal = st.text_input("Inscrição Municipal", placeholder="Ex: 123456")

st.markdown("---") # Linha divisória

# --- FUNÇÕES (MANTIDAS IGUAIS) ---
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

def converter_arquivo(conteudo_arquivo):
    notas = []
    padrao_rps = re.compile(r'(200\s+\d+.*?)(?=200\s+\d|900\d|$)', re.DOTALL)
    matches = padrao_rps.findall(conteudo_arquivo)
    
    for bloco in matches:
        linha_limpa = bloco.replace('\n', '').replace('\r', '')
        match_rps = re.search(r'200\s+0+(\d+)', linha_limpa)
        num_rps = match_rps.group(1) if match_rps else "0"
        match_data = re.search(r'(20\d{6})', linha_limpa)
        data_emissao = match_data.group(1) if match_data else "20260101"
        match_valor = re.findall(r'000(\d{3,15})', linha_limpa)
        valor_servico = match_valor[-2] if len(match_valor) > 1 else "0"
        
        # Lógica de descrição melhorada
        partes = linha_limpa.split('Serviços prestados')
        if len(partes) > 1:
            desc = "Serviços prestados" + partes[1]
        else:
            # Tenta pegar tudo após o código do serviço se não achar a frase padrão
            desc = "Serviços de Agenciamento e Outros"
            
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
    
    # Usa os dados digitados nos campos novos
    cnpj_limpo = re.sub(r'\D', '', cnpj_prestador) if cnpj_prestador else "00000000000000"
    
    ET.SubElement(lote_rps, 'Cnpj').text = cnpj_limpo
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
        ET.SubElement(prestador, 'Cnpj').text = cnpj_limpo
        ET.SubElement(prestador, 'InscricaoMunicipal').text = inscricao_municipal
        tomador = ET.SubElement(inf_rps, 'Tomador')
        ident_tomador = ET.SubElement(tomador, 'IdentificacaoTomador')
        cpf_cnpj = ET.SubElement(ident_tomador, 'CpfCnpj')
        doc_limpo = nota['tomador_doc'].strip()
        if len(doc_limpo) > 11:
            ET.SubElement(cpf_cnpj, 'Cnpj').text = doc_limpo
        else:
            ET.SubElement(cpf_cnpj, 'Cpf').text = doc_limpo

    return minidom.parseString(ET.tostring(lote)).toprettyxml(indent="   ").encode('utf-8')

# --- AREA DE UPLOAD ---
st.markdown("### 📂 Selecione o arquivo")
uploaded_file = st.file_uploader("Arraste o TXT da Nota Carioca aqui", type=['txt'])

if uploaded_file is not None:
    # Verificação de segurança: Só deixa converter se preencheu o CNPJ
    if len(cnpj_prestador) < 10:
        st.error("⚠️ Por favor, preencha o CNPJ do Prestador acima antes de converter.")
    else:
        string_data = uploaded_file.getvalue().decode("latin-1")
        if st.button("🔄 Converter Arquivo Agora", type="primary"):
            with st.spinner('Processando...'):
                try:
                    notas = converter_arquivo(string_data)
                    if not notas:
                        st.warning("O arquivo parece vazio ou fora do padrão.")
                    else:
                        st.success(f"✅ Sucesso! {len(notas)} notas identificadas.")
                        xml_bytes = gerar_xml(notas)
                        st.download_button(
                            label="⬇️ BAIXAR XML PRONTO (GOV.BR)",
                            data=xml_bytes,
                            file_name="Lote_Convertido_Nacional.xml",
                            mime="application/xml",
                            use_container_width=True
                        )
                except Exception as e:
                    st.error(f"Erro técnico: {e}")