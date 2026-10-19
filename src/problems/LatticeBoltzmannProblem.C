/**********************************************************************/
/*                     DO NOT MODIFY THIS HEADER                      */
/*            Marlin, a Fourier spectral solver for MOOSE             */
/*                                                                    */
/*            Copyright 2024 Battelle Energy Alliance, LLC            */
/*                        ALL RIGHTS RESERVED                         */
/**********************************************************************/

#include "LatticeBoltzmannProblem.h"
#include "LatticeBoltzmannStencilBase.h"

#include "TensorSolver.h"
#include "TensorOperatorBase.h"
#include "TensorOutput.h"
#include "DomainAction.h"

#include "MarlinUtils.h"
#include "DependencyResolverInterface.h"

#include "Executioner.h"

registerMooseObject("MarlinApp", LatticeBoltzmannProblem);

InputParameters
LatticeBoltzmannProblem::validParams()
{
  InputParameters params = TensorProblem::validParams();
  params.addParam<TensorInputBufferName>(
      "binary_media",
      "Integer tensor buffer defining solid/fluid regions for complex geometries. "
      "Values: 0 = solid (closed cell, no flow), 1 = fluid (open cell, flow allowed). "
      "Internal solid boundaries must use 'boundary = wall' in boundary conditions. "
      "Domain edge boundaries (top/bottom/left/right/front/back) are specified separately.");

  params.addParam<TensorInputBufferName>(
      "residual_tensor",
      "Tensor buffer used to monitor convergence (e.g. speed, density, order parameter). "
      "When provided, residual is computed every log_interval substeps as the relative "
      "change in the L1 norm of this field.");
  params.addParam<unsigned int>("substeps", 1, "Number of LBM iterations for every MOOSE timestep");
  params.addParam<unsigned int>("log_interval", 1, "Interval for logging LBM substep information");
  params.addParam<Real>("tolerance", 1.0e-10, "LBM convergence tolerance");
  params.addClassDescription("Problem object to enable solving lattice Boltzmann problems");

  return params;
}

LatticeBoltzmannProblem::LatticeBoltzmannProblem(const InputParameters & parameters)
  : TensorProblem(parameters),
    _is_binary_media(isParamValid("binary_media")),
    _is_residual_compute(isParamValid("residual_tensor")),
    _lbm_substeps(getParam<unsigned int>("substeps")),
    _log_interval(getParam<unsigned int>("log_interval")),
    _tolerance(getParam<Real>("tolerance"))
{
  if (_domain.comm().size() > 1)
    _ghost_radius = 1;

  // fix sizes
  std::vector<int64_t> shape(_domain.getLocalGridSize().begin(), _domain.getLocalGridSize().end());
  if (shape.size() < 3)
    shape.push_back(1);
  for (const auto i : index_range(shape))
  {
    _shape_extended.push_back(shape[i]);
    _shape_extended_to_q.push_back(shape[i]);
  }
}

void
LatticeBoltzmannProblem::init()
{
  TensorProblem::init();

  // dependency resolution of boundary conditions
  DependencyResolverInterface::sort(_bcs);

  // cache reference to residual monitoring tensor
  if (_is_residual_compute)
    _residual_tensor = getBuffer(getParam<TensorInputBufferName>("residual_tensor"), _ghost_radius);

  // binary mesh if provided
  if (_is_binary_media)
  {
    _binary_media = getBuffer(getParam<TensorInputBufferName>("binary_media"), _ghost_radius);

    _binary_media_owned = _binary_media;
    for (unsigned int d = 0; d < _dim; d++)
      _binary_media_owned = _binary_media_owned.narrow(d, _ghost_radius, _shape_extended[d]);

    exchangeGhostLayers(getParam<TensorInputBufferName>("binary_media"), _ghost_radius);
  }
}

void
LatticeBoltzmannProblem::execute(const ExecFlagType & exec_type)
{
  if (exec_type == EXEC_INITIAL)
  {
    // check for constants
    if (_fetched_constants.size() == 1)
      mooseError(
          "Constant ", Moose::stringify(_fetched_constants), " was requested but never declared.");
    if (_fetched_constants.size() > 1)
      mooseError("Constants ",
                 Moose::stringify(_fetched_constants),
                 " were requested but never declared.");
    _can_fetch_constants = false;

    // update time
    _sub_time = FEProblem::time();

    executeTensorInitialConditions();

    // if the binary mesh is updated at initial conditions
    // in the future we need a better way to handle this
    if (_is_binary_media)
      _binary_media = getBuffer(getParam<TensorInputBufferName>("binary_media"));

    // the media is fixed from here on, so build the solid mask used by maskedFillSolids once
    if (_is_binary_media)
    {
      _solid_mask = (_binary_media_owned == 0);
      _solid_index = torch::nonzero(_solid_mask.flatten()).squeeze(1);
    }

    executeTensorOutputs(EXEC_INITIAL);
  }

  if (exec_type == EXEC_TIMESTEP_BEGIN && timeStep() > 1)
    for (unsigned substep = 0; substep < _lbm_substeps; substep++)
    {
      // create old state buffers
      advanceState();

      // run solver for streaming
      if (_solver)
        _solver->computeBuffer();

      // run bcs
      for (auto & bc : _bcs)
        bc->realSpaceComputeBuffer();

      // run computes
      for (auto & cmp : _computes)
        cmp->computeBuffer();

      if (_is_residual_compute && substep % _log_interval == 0)
      {
        computeLBMResidual();
        if (std::isnan(_convergence_residual))
        {
          _console << COLOR_RED << "Aborting at Lattice Boltzmann Substep " << substep
                   << ", Residual " << _convergence_residual << COLOR_DEFAULT << std::endl;
          getMooseApp().getExecutioner()->fixedPointSolve().failStep();
          break;
        }
        _console << COLOR_WHITE << "Lattice Boltzmann Substep " << substep << ", Residual "
                 << _convergence_residual << COLOR_DEFAULT << std::endl;
      }

      _t_total++;

      if (_convergence_residual < _tolerance)
        return;
    }

  if (exec_type == EXEC_TIMESTEP_END)
    executeTensorOutputs(EXEC_TIMESTEP_END);

  // mapBuffersToAux();
  FEProblem::execute(exec_type);
}

void
LatticeBoltzmannProblem::computeLBMResidual()
{
  torch::Tensor owned = _residual_tensor;
  for (unsigned int d = 0; d < _dim; d++)
    owned = owned.narrow(d, _ghost_radius, _shape_extended[d]);

  if (_residual_tensor_previous.numel() == 0)
  {
    _residual_tensor_previous = owned.clone();
    _convergence_residual = 1.0;
    return;
  }

  // both sums in one device-to-host transfer and one reduction
  const auto current = owned.sum();
  _residual_tensor_previous.sub_(owned).abs_();
  const auto sums_cpu =
      torch::stack({current, _residual_tensor_previous.sum()}).to(torch::kCPU, torch::kFloat64);
  std::vector<Real> sums{sums_cpu[0].item<Real>(), sums_cpu[1].item<Real>()};
  _domain.comm().sum(sums);
  const Real sum_current = sums[0];
  const Real sum_diff = sums[1];

  _convergence_residual = (sum_current == 0 || sum_diff == 0) ? 1.0 : sum_diff / sum_current;

  _residual_tensor_previous.copy_(owned);
}

void
LatticeBoltzmannProblem::addTensorBoundaryCondition(const std::string & compute_type,
                                                    const std::string & name,
                                                    InputParameters & parameters)
{
  addTensorCompute(compute_type, name, parameters, _bcs);
}

void
LatticeBoltzmannProblem::addStencil(const std::string & stencil_name,
                                    const std::string & name,
                                    InputParameters & parameters)
{
  if (_stencil_counter > 0)
    mooseError("Problem object LatticeBoltzmannProblem can only have one stencil");
  // Create the object
  _stencil = _factory.create<LatticeBoltzmannStencilBase>(stencil_name, name, parameters, 0);
  _stencil_counter++;
  logAdd("LatticeBoltzmannStencilBase", name, stencil_name, parameters);

  _shape_extended_to_q.push_back(_stencil->_q);
}

void
LatticeBoltzmannProblem::maskedFillSolids(torch::Tensor & t, const Real & value)
{
  if (!_is_binary_media)
    return;

  // fast path for contiguous tensors over the owned nodes: fill only the solid rows, so the cost
  // scales with the number of solid nodes instead of every entry of t
  if (value == 0 && _solid_index.defined() && t.is_contiguous() &&
      t.dim() >= _solid_mask.dim() && t.sizes().slice(0, _solid_mask.dim()) == _solid_mask.sizes())
  {
    t.view({_solid_mask.numel(), -1}).index_fill_(0, _solid_index, value);
    return;
  }

  // use the cached mask once it exists (it is built for the solid marker 0 only)
  const auto solid_mask =
      (value == 0 && _solid_mask.defined()) ? _solid_mask : (_binary_media_owned == value);

  if (t.dim() == solid_mask.dim())
    // 3D
    t.masked_fill_(solid_mask, value);
  else
    // 2D and 1D
    t.masked_fill_(solid_mask.unsqueeze(-1).expand(t.sizes()), value);
}
