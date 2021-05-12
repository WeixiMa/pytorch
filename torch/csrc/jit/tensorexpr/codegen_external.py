#!/usr/bin/env python3
from tools.codegen.gen import parse_native_yaml
import tools.codegen.model as model
from tools.codegen.code_template import CodeTemplate

def deindent(code: str) -> str:
    lines = code.split('\n')
    min_leading_spaces = min(map(num_leading_spaces, lines))
    lines = [line[min_leading_spaces:] for line in lines]
    return '\n'.join(lines)

path = "/home/chilli/fb/pytorch/aten/src/ATen/native/native_functions.yaml"
native_functions = parse_native_yaml(path)
func_decls = []
for schema in native_functions:
    func = schema.func
    name = func.name.name.base
    args = func.arguments
    # Only supports extern calls for functions with out variants
    if func.name.overload_name != 'out':
        continue

    # Doesn't currently support functions with more than one out parameter
    if len(args.out) > 1:
        continue

    # Doesn't currently support kwarg arguments
    if len(args.pre_tensor_options_kwarg_only) > 0 or len(args.post_tensor_options_kwarg_only) > 0:
        continue
    self_arg = [args.self_arg.argument] if args.self_arg is not None else []
    args = list(args.pre_self_positional) + self_arg + list(args.post_self_positional)
    tensor_args = [arg for arg in args if isinstance(arg.type, model.BaseType) and arg.type.name == model.BaseTy.Tensor]
    if len(tensor_args) != len(args):
        continue

    arg_names = [None] * len(args)

    tensor_decls = []
    for idx, arg in enumerate(tensor_args):
        s = f"const at::Tensor& {arg.name} = tensors[{idx + 1}];"
        tensor_decls.append(s)
        arg_names[idx] = arg.name
    nl = '\n  '

    # print(tensor_decls, name, arg_names)
    func_decl = f"""
void nnc_aten_{name}(
    int64_t bufs_num,
    void** buf_data,
    int64_t* buf_ranks,
    int64_t* buf_dims,
    int8_t* buf_dtypes,
    int64_t args_num,
    int64_t* extra_args) {{
  std::vector<at::Tensor> tensors =
        constructTensors(bufs_num, buf_data, buf_ranks, buf_dims, buf_dtypes);
  at::Tensor& r = tensors[0];
  {nl.join(tensor_decls)}
  try {{
    at::{name}_out({', '.join(['r'] + arg_names)});
  }} catch(...) {{
  }}
}}
const static RegisterNNCExternalFunction nnc_{name}(
     "nnc_aten_{name}",
     nnc_aten_{name});
"""
    func_decls.append(func_decl)
external_path = "external_functions_template.cpp"
code_template = CodeTemplate.from_file(external_path)
with open('external_functions.cpp', 'w') as f:
    f.write(code_template.substitute(external_functions=func_decls))
