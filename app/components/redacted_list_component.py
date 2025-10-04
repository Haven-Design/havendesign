import streamlit as st
import streamlit.components.v1 as components
import os

_component_func = components.declare_component(
    "redacted_list",
    path=os.path.join(os.path.dirname(__file__), "redacted_list/frontend/dist"),
)

def redacted_list(data, key=None):
    return _component_func(data=data, default={}, key=key)
