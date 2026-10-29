"""Causality, qualification and intervention checks; no human efficacy claims."""
import unittest
from dataclasses import replace, fields
import numpy as np

from scci_rh.stage3.acquisition import AcquisitionConfig, ContactAcquisition, NeuralFeatures, artifact_coverage
from scci_rh.stage3.electrical import MotorDelivery
from scci_rh.stage3.motor import (MotorConfig, Observation, StateEstimate, LearnerMap,
                             ExpertRepresentation, CausalDecoder, _World, _pulse,
                             _capture, calibrate, control_request, run_study)


def feature_packet(now=.5):
    return NeuralFeatures((0.,)*32, now-.020, now-.000205, now-.010,
                          1., True, (), 320, 0, 0, now, 1.)


def identified_map():
    return LearnerMap(((.06,0.),(0.,.06)), ((.002,0.),(0.,.002)),
                      .035,.005,True,(),200,1.,.0005,.001)


class AcquisitionContracts(unittest.TestCase):
    def test_16_by_4khz_packet_has_aperture_support_before_arrival(self):
        acquisition = ContactAcquisition(5)
        packet = acquisition.observe(0., [0.,0.], [0.,0.])
        self.assertEqual(packet.acquired_samples, 16*20)
        self.assertAlmostEqual(packet.available_time_s,.005)
        self.assertAlmostEqual(packet.support_end_s,.004795)
        self.assertLess(packet.support_end_s,packet.available_time_s)
        self.assertEqual(len(packet.values_uv),32)
        self.assertFalse(packet.valid)
        self.assertIn("WARMUP",packet.reasons)

    def test_filter_history_outlasts_raw_mask_support(self):
        acquisition = ContactAcquisition(7)
        for k in range(60):
            acquisition.observe(k*.005,[0.,0.],[0.,0.])
        bad = acquisition.observe(.300,[0.,0.],[0.,0.],extra_saturation=True)
        self.assertFalse(bad.valid)
        for k in range(61,66):
            packet = acquisition.observe(k*.005,[0.,0.],[0.,0.])
        self.assertEqual(packet.usable_fraction,1.)
        self.assertFalse(packet.valid)
        self.assertIn("FILTER_HISTORY_UNQUALIFIED",packet.reasons)
        for k in range(66,86):
            packet = acquisition.observe(k*.005,[0.,0.],[0.,0.])
        self.assertTrue(packet.valid)

    def test_periodic_raw_coverage_cannot_certify_recursive_state(self):
        audit = artifact_coverage()
        self.assertGreater(audit["minimum_20ms_usable_fraction"],.9)
        self.assertEqual(audit["qualified_feature_fraction_after_warmup"],0.)
        self.assertGreater(audit["raw_mask_fraction"],0.)

    def test_time_gap_requires_new_history_not_implicit_missing_samples(self):
        acquisition = ContactAcquisition(8)
        for k in range(30):
            good=acquisition.observe(k*.005,[0.,0.],[0.,0.])
        self.assertTrue(good.valid)
        gap=acquisition.observe(.25,[0.,0.],[0.,0.])
        self.assertIn("WARMUP",gap.reasons)
        with self.assertRaises(ValueError):
            acquisition.observe(.24,[0.,0.],[0.,0.])


class MotorInformationContracts(unittest.TestCase):
    def test_world_state_is_not_backdated_into_acquisition_block(self):
        observations,records,_,_=_capture(1,MotorConfig(),.10)
        self.assertEqual(records[0]["simulator_position_m"],[0.,0.])
        for observation in observations:
            self.assertLessEqual(observation.neural.available_time_s,observation.available_time_s)
            self.assertLess(observation.neural.support_end_s,observation.available_time_s)
            self.assertAlmostEqual(observation.available_time_s-observation.external_measurement_time_s,.025)
        names={f.name for f in fields(Observation)}
        self.assertFalse({"theta","recruitment","true_phase_charge_C"}&names)

    def test_nonfinite_future_or_reversed_external_support_is_rejected(self):
        decoder=CausalDecoder(MotorConfig())
        packet=feature_packet()
        for time,position in ((.51,(0.,0.)),(.48,(float('nan'),0.))):
            estimate=decoder.estimate(Observation(.5,position,time,True,packet),"external")
            self.assertFalse(estimate.valid)
        decoder.estimate(Observation(.5,(0.,0.),.48,True,packet),"external")
        reversed_record=decoder.estimate(Observation(.505,(0.,0.),.475,True,packet),"external")
        self.assertEqual(reversed_record.reason,"EXTERNAL_NONMONOTONIC")

    def test_duplicate_external_packet_does_not_invent_new_measurement(self):
        decoder=CausalDecoder(MotorConfig())
        for now in (.5,.505,.51):
            decoder.estimate(Observation(now,(0.,0.),.48,True,feature_packet(now)),"external")
        self.assertEqual(len(decoder._external),1)

    def test_replayed_neural_features_cannot_fuse_with_fresh_external(self):
        model={"mean":np.zeros(32),"scale":np.ones(32),"weights":np.zeros((33,4)),
               "rmse":.001,"velocity_rmse":.01}
        decoder=CausalDecoder(MotorConfig(),model)
        old=feature_packet(.48)
        for now in (.50,.505,.51):
            stale=decoder.estimate(Observation(now,(0.,0.),now-.02,True,old),"neural_external")
        self.assertEqual(stale.source,"EXTERNAL")
        fresh=decoder.estimate(Observation(.515,(0.,0.),.495,True,feature_packet(.515)),"neural_external")
        self.assertEqual(fresh.source,"NEURAL_PLUS_SAME_EXTERNAL")

    def test_post_delivery_veto_retains_body_dose_and_monitor_uncertainty(self):
        def failed_delivery(request):
            q=request["command_current_A"]*request["phase_s"]
            return {"true_phase_charge_C":q,"delivered_phase_charge_C":q*.9,
                    "charge_uncertainty_C":q*.5,"quality":"DELIVERED_UNQUALIFIED",
                    "inhibit_next":True}
        truth,qualified,monitor,_=_pulse(0,0,1,failed_delivery,MotorConfig())
        self.assertEqual(truth,1.)
        self.assertEqual(qualified,0.)
        self.assertGreater(monitor["delivered_phase_charge_C"],0.)
        self.assertTrue(monitor["inhibit_next"])
        self.assertNotIn("true_phase_charge_C",monitor)

    def test_unavailable_expert_and_future_state_abstain(self):
        c=MotorConfig()
        state=StateEstimate((0.,0.),(0.,0.),.48,.008,True,"EXTERNAL","TEST")
        expert=ExpertRepresentation("expert_neural",((.1,0.,0.,0.),(-.1,0.,0.,0.)),
                                    .01,"none","none",0.,False,"UNAVAILABLE")
        request,reason=control_request(state,identified_map(),expert,.5,c)
        np.testing.assert_array_equal(request,[0.,0.])
        self.assertEqual(reason,"UNAVAILABLE_EXPERT_REPRESENTATION")
        future=replace(state,support_time_s=.6)
        _,reason=control_request(future,identified_map(),replace(expert,qualified=True),.5,c)
        self.assertEqual(reason,"NONFINITE_OR_FUTURE_INPUT")


class MotorLearningMechanisms(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config=MotorConfig(practice_blocks=1,practice_block_s=1.,assessment_s=1.,
                               calibration_s=3.,motor_onset_delay_s=.005)
        cls.conditional=run_study(2,cls.config,families=("favorable","zero","dependent","harmful"),
                                  conditions=("observe_only","neural_external__expert_neural"))
        cls.actual_map,_,cls.actual_calibration=calibrate(0,cls.config,MotorDelivery())

    def test_actual_measurement_bound_can_reject_identified_authority(self):
        self.assertGreater(self.actual_calibration["measured_dose_uncertainty_fraction"],.4)
        self.assertFalse(self.actual_map.qualified)
        self.assertLess(self.actual_calibration["authority_singular_margin_m"],0.)
        self.assertLess(self.actual_map.heldout_response_rmse_m,.005)

    def test_nominal_conditional_mechanism_is_labeled_and_does_not_force_null_gain(self):
        r=self.conditional
        self.assertEqual(r["delivery_model"],"UNQUALIFIED_NOMINAL_ASSUMPTION")
        zero=r["families"]["zero"]["conditions"]
        baseline=zero["observe_only"]["summary"]["retention_off"]["trajectory_rmse_m"]
        assisted=zero["neural_external__expert_neural"]["summary"]["retention_off"]["trajectory_rmse_m"]
        self.assertAlmostEqual(baseline,assisted,places=13)
        self.assertGreater(zero["neural_external__expert_neural"]["practice_blocks"][0]["pulse_count"],0)

    def test_all_retention_and_transfer_assessments_have_output_off(self):
        for family in self.conditional["families"].values():
            for condition in family["conditions"].values():
                summary=condition["summary"]
                self.assertTrue(summary["assistance_off_verified"])
                for assessment in ("retention_off","transfer_off"):
                    self.assertEqual(summary[assessment]["pulse_count"],0)
                    self.assertEqual(summary[assessment]["assistance"],"OFF")
                self.assertEqual(summary["practice_seconds"],1.)

    def test_four_plasticity_families_are_distinct_equations(self):
        c=MotorConfig(motor_onset_delay_s=.005)
        outcomes={}
        for family in ("favorable","zero","dependent","harmful"):
            world=_World(3,c)
            for k in range(100):
                world.advance(k*c.dt_s,[1.,1.],family,learning=True)
            outcomes[family]=world.theta.copy()
        for a,b in (("favorable","zero"),("zero","dependent"),("dependent","harmful")):
            self.assertGreater(np.linalg.norm(outcomes[a]-outcomes[b]),1e-5)


if __name__ == "__main__":
    unittest.main()
