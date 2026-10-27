/**********************************************************************/
/*                     DO NOT MODIFY THIS HEADER                      */
/*            Marlin, a Fourier spectral solver for MOOSE             */
/*                                                                    */
/*            Copyright 2024 Battelle Energy Alliance, LLC            */
/*                        ALL RIGHTS RESERVED                         */
/**********************************************************************/

#include "LBMEquilibrium.h"
#include "LBMProfile.h"

registerMooseObject("MarlinApp", LBMEquilibrium);

InputParameters
LBMEquilibrium::validParams()
{
  InputParameters params = LatticeBoltzmannOperator::validParams();
  params.addClassDescription("Compute LB equilibrium distribution object.");
  params.addRequiredParam<TensorInputBufferName>(
      "bulk", "LBM bluk macroscpic parameter, e.g density or temperature");
  params.addRequiredParam<TensorInputBufferName>("velocity",
                                                 "LBM Velocty in x, y and z directions");
  return params;
}

LBMEquilibrium::LBMEquilibrium(const InputParameters & parameters)
  : LatticeBoltzmannOperator(parameters),
    _rho(getInputBuffer("bulk", _radius)),
    _velocity(getInputBuffer("velocity", _radius))
{
}

void
LBMEquilibrium::computeBuffer()
{
  // TEMPORARY per-line profiling (only the Solve compute named 'equilibrium')
  const bool prof = name() == "equilibrium";
  double t0 = prof ? LBMProfile::now() : 0.0, t1;
#define LINE_TIMER(label)                                                                          \
  if (prof)                                                                                        \
  {                                                                                                \
    t1 = LBMProfile::now();                                                                        \
    LBMProfile::add(label, t1 - t0);                                                               \
    t0 = t1;                                                                                       \
  }

  const unsigned int dim = _domain.getDim();
  const int64_t N = _u.numel() / _stencil._q;
  const int Q = _stencil._q;

  auto vel_flat = _velocity.slice(/*dim=*/-1, /*start=*/0, /*end=*/dim).reshape({N, dim});
  auto rho_flat = _rho.reshape({N, 1});
  auto u_flat = _u.view({N, Q});
  auto w_flat = _w.view({1, Q});
  LINE_TIMER("L35-42 views/reshapes");

  // |u|^2 as elementwise ops: a sum() over an inner dimension of 2-3 is a very slow reduction
  auto usqr = vel_flat.select(1, 0).square();
  for (const auto d : make_range(1u, dim))
    usqr.add_(vel_flat.select(1, d).square());
  usqr = usqr.unsqueeze(1);
  LINE_TIMER("L44 usqr = elementwise");
  auto edotu = torch::mm(vel_flat, _e_mat.t());
  LINE_TIMER("L45 edotu = mm(vel, e^T)");

  torch::square_out(u_flat, edotu).div_(2.0 * _lb_problem._cs4);
  LINE_TIMER("L47 square_out + div_");
  u_flat.add_(edotu, /*alpha=*/1.0 / _lb_problem._cs2);
  LINE_TIMER("L48 add_(edotu)");
  u_flat.sub_(usqr, /*alpha=*/1.0 / (2.0 * _lb_problem._cs2));
  LINE_TIMER("L49 sub_(usqr)");
  u_flat.add_(1.0);
  LINE_TIMER("L50 add_(1)");

  u_flat.mul_(w_flat);
  LINE_TIMER("L52 mul_(w)");
  u_flat.mul_(rho_flat);
  LINE_TIMER("L53 mul_(rho)");

  _u_owned = ownedView(_u);
  _lb_problem.maskedFillSolids(_u_owned, 0);
  LINE_TIMER("L55-56 ownedView + maskedFillSolids");
#undef LINE_TIMER
}
